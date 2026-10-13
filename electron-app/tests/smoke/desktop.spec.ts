import fs from "node:fs";
import path from "node:path";

import {
  _electron as electron,
  expect,
  test,
  type BrowserContext,
  type ElectronApplication,
  type Route,
} from "@playwright/test";

const backendUrl = "http://127.0.0.1:8010/api/v1";
const healthCheckUrl = new URL("/health", new URL(backendUrl).origin).toString();
const proxiedBackendRoutePatterns: ReadonlyArray<string | RegExp> = [
  "**/api/v1/**",
  /\/health(?:\?.*)?$/,
];
const packagedAppDirectory = path.resolve(process.cwd(), "release", "linux-unpacked");
const packagedRendererDirectory = path.resolve(
  process.cwd(),
  "release",
  "linux-unpacked",
  "resources",
  "renderer",
);
const desktopConfigPath = path.resolve(
  process.cwd(),
  "release",
  "linux-unpacked",
  "desktop-public.json",
);
const desktopRendererBuildConfigPath = path.resolve(
  packagedRendererDirectory,
  "desktop-public-build.json",
);
const smokeProfileRoot = path.resolve(process.cwd(), "test-results");
type DisposeApiProxy = (closeApp: () => Promise<void>) => Promise<void>;
type ApiProxyController = {
  dispose: DisposeApiProxy;
  waitForSuccessfulHealthCheck: () => Promise<void>;
  waitForSuccessfulReviewInboxResponse: () => Promise<void>;
};

const closeWithoutApiProxy: DisposeApiProxy = async (closeApp) => {
  await closeApp();
};

const authLabels = {
  localIdentifier: /Identifiant local|Local identifier/,
  displayName: /Nom affiché|Display name/,
  selectIdentity: /Sélectionner l’identité|Select identity/,
  openWorkspace: /Ouvrir|Open/,
};

function resolvePackagedAppPath() {
  const candidates = [
    path.join(packagedAppDirectory, "electron-app"),
    path.join(packagedAppDirectory, "AI Value Studio Desktop"),
  ];

  return candidates.find((candidate) => fs.existsSync(candidate)) ?? candidates[0];
}

function prepareDesktopConfigForSmoke() {
  if (!fs.existsSync(desktopRendererBuildConfigPath)) {
    throw new Error(
      `Missing packaged renderer build metadata at ${desktopRendererBuildConfigPath}. Rebuild the dev renderer and repack the desktop app before running smoke tests.`,
    );
  }

  const packagedRendererBuildConfigRaw = fs.readFileSync(desktopRendererBuildConfigPath, "utf8");
  let packagedRendererBuildConfig: unknown;

  try {
    packagedRendererBuildConfig = JSON.parse(packagedRendererBuildConfigRaw);
  } catch (error) {
    throw new Error(
      `Invalid JSON in packaged renderer build metadata at ${desktopRendererBuildConfigPath}.`,
      { cause: error },
    );
  }

  if (
    !packagedRendererBuildConfig ||
    typeof packagedRendererBuildConfig !== "object" ||
    Array.isArray(packagedRendererBuildConfig)
  ) {
    throw new Error(
      `Expected packaged renderer build metadata at ${desktopRendererBuildConfigPath} to be a JSON object.`,
    );
  }

  const { authMode, apiBaseUrl } = packagedRendererBuildConfig as {
    apiBaseUrl?: unknown;
    authMode?: unknown;
  };

  if (authMode !== "dev") {
    throw new Error(
      `Expected packaged renderer build metadata at ${desktopRendererBuildConfigPath} to use authMode "dev", got ${JSON.stringify(authMode)}. Rebuild web/out in dev mode and run \`npm run pack\` again.`,
    );
  }

  if (apiBaseUrl !== backendUrl) {
    throw new Error(
      `Expected packaged renderer build metadata at ${desktopRendererBuildConfigPath} to use apiBaseUrl ${JSON.stringify(backendUrl)}, got ${JSON.stringify(apiBaseUrl)}. Rebuild web/out with NEXT_PUBLIC_API_BASE_URL=${backendUrl} and run \`npm run pack\` again.`,
    );
  }

  fs.mkdirSync(path.dirname(desktopConfigPath), { recursive: true });
  fs.writeFileSync(desktopConfigPath, packagedRendererBuildConfigRaw, "utf8");
}

function createSmokeHomeDirectory() {
  fs.mkdirSync(smokeProfileRoot, { recursive: true });
  return fs.mkdtempSync(path.join(smokeProfileRoot, "smoke-home-"));
}

async function proxyApiRequests(context: BrowserContext): Promise<ApiProxyController> {
  const pendingRoutes = new Set<Promise<void>>();
  const abortControllers = new Set<AbortController>();
  const observedHealthRequests: string[] = [];
  const observedHealthResponses: string[] = [];
  const observedHealthFailures: string[] = [];
  const observedReviewInboxResponses: string[] = [];
  let isCleaningUp = false;
  let successfulHealthCheckObserved = false;
  let successfulReviewInboxResponseObserved = false;

  const recordHealthRequest = (requestUrl: string) => {
    if (new URL(requestUrl).pathname === "/health") {
      observedHealthRequests.push(requestUrl);
    }
  };

  const handleRequest = (request: { url(): string }) => {
    recordHealthRequest(request.url());
  };

  const handleResponse = (response: { url(): string; status(): number }) => {
    const responseUrl = response.url();
    if (new URL(responseUrl).pathname === "/health") {
      observedHealthResponses.push(`${response.status()} ${responseUrl}`);
    }
  };

  const handleRequestFailed = (request: { url(): string; failure(): { errorText: string } | null }) => {
    const requestUrl = request.url();
    if (new URL(requestUrl).pathname === "/health") {
      observedHealthFailures.push(
        `${request.failure()?.errorText ?? "request failed"} ${requestUrl}`,
      );
    }
  };

  context.on("request", handleRequest);
  context.on("response", handleResponse);
  context.on("requestfailed", handleRequestFailed);

  const isExpectedCleanupError = (error: unknown) => {
    if (!isCleaningUp) {
      return false;
    }

    const message = error instanceof Error ? error.message : String(error);
    return (
      message.includes("This operation was aborted") ||
      message.includes("Request context disposed") ||
      message.includes("Target page, context or browser has been closed") ||
      message.includes("Route is already handled")
    );
  };

  const handleRoute = (route: Route) => {
    const pendingRoute = (async () => {
      const browserRequest = route.request();
      const url = new URL(browserRequest.url());
      const abortController = new AbortController();
      const requestBodyBuffer = browserRequest.postDataBuffer();

      recordHealthRequest(url.toString());
      abortControllers.add(abortController);

      try {
        const response = await fetch(`http://127.0.0.1:8010${url.pathname}${url.search}`, {
          method: browserRequest.method(),
          headers: browserRequest.headers(),
          body:
            browserRequest.method() === "GET" || browserRequest.method() === "HEAD"
              ? undefined
              : requestBodyBuffer
                ? new Uint8Array(requestBodyBuffer)
                : undefined,
          signal: abortController.signal,
        });
        const body = Buffer.from(await response.arrayBuffer());

        if (url.pathname === "/health" && response.ok) {
          successfulHealthCheckObserved = true;
        }
        if (url.pathname.includes("/review-inbox") && response.ok) {
          successfulReviewInboxResponseObserved = true;
          observedReviewInboxResponses.push(`${response.status} ${url.toString()}`);
        }

        await route.fulfill({
          body,
          headers: Object.fromEntries(response.headers.entries()),
          status: response.status,
        });
      } catch (error) {
        if (isExpectedCleanupError(error)) {
          return;
        }

        throw error;
      } finally {
        abortControllers.delete(abortController);
      }
    })();

    pendingRoutes.add(pendingRoute);
    void pendingRoute.finally(() => {
      pendingRoutes.delete(pendingRoute);
    });

    return pendingRoute;
  };

  await Promise.all(
    proxiedBackendRoutePatterns.map((routePattern) => context.route(routePattern, handleRoute)),
  );

  return {
    waitForSuccessfulHealthCheck: async () => {
      const timeoutAt = Date.now() + 15_000;
      while (!successfulHealthCheckObserved && Date.now() < timeoutAt) {
        await new Promise((resolve) => setTimeout(resolve, 100));
      }

      if (!successfulHealthCheckObserved) {
        throw new Error(
          `expected successful desktop health proxy via ${healthCheckUrl}; requests=${JSON.stringify(observedHealthRequests)} responses=${JSON.stringify(observedHealthResponses)} failures=${JSON.stringify(observedHealthFailures)}`,
        );
      }
    },
    waitForSuccessfulReviewInboxResponse: async () => {
      const timeoutAt = Date.now() + 15_000;
      while (!successfulReviewInboxResponseObserved && Date.now() < timeoutAt) {
        await new Promise((resolve) => setTimeout(resolve, 100));
      }

      if (!successfulReviewInboxResponseObserved) {
        throw new Error(
          `expected successful review inbox response via ${backendUrl}; responses=${JSON.stringify(observedReviewInboxResponses)}`,
        );
      }
    },
    dispose: async (closeApp: () => Promise<void>) => {
      isCleaningUp = true;
      context.off("request", handleRequest);
      context.off("response", handleResponse);
      context.off("requestfailed", handleRequestFailed);
      for (const abortController of abortControllers) {
        abortController.abort();
      }
      await context.unrouteAll({ behavior: "ignoreErrors" });
      await closeApp();

      const settledRoutes = await Promise.allSettled(Array.from(pendingRoutes));
      const rejectedRoute = settledRoutes.find(
        (result): result is PromiseRejectedResult =>
          result.status === "rejected" && !isExpectedCleanupError(result.reason),
      );

      if (rejectedRoute) {
        throw rejectedRoute.reason;
      }
    },
  };
}

async function waitForFirstWindow(electronApp: ElectronApplication) {
  try {
    return await electronApp.firstWindow();
  } catch (error) {
    const browserWindows = await electronApp.evaluate(({ BrowserWindow }) =>
      BrowserWindow.getAllWindows().map((browserWindow) => ({
        destroyed: browserWindow.isDestroyed(),
        title: browserWindow.getTitle(),
        visible: browserWindow.isVisible(),
      })),
    );

    throw new Error(
      `Timed out waiting for the packaged desktop window. BrowserWindows=${JSON.stringify(browserWindows)}`,
      { cause: error },
    );
  }
}

async function closeElectronApp(electronApp: ElectronApplication | null) {
  if (!electronApp) {
    return;
  }

  const appClosed =
    electronApp.process().exitCode === null ? electronApp.waitForEvent("close") : Promise.resolve();

  await electronApp.close();
  await appClosed;
}

test("launches the packaged Linux desktop shell in dev auth mode and opens a workspace", async () => {
  test.skip(process.platform !== "linux", "Smoke covers the packaged Linux executable only.");

  const packagedAppPath = resolvePackagedAppPath();
  expect(fs.existsSync(packagedAppPath)).toBe(true);
  await test.step("verify packaged renderer metadata and write matching desktop config", () => {
    prepareDesktopConfigForSmoke();
  });
  const smokeHomeDirectory = createSmokeHomeDirectory();
  let electronApp: ElectronApplication | null = null;
  let disposeApiProxy: DisposeApiProxy = closeWithoutApiProxy;
  let waitForSuccessfulHealthCheck: () => Promise<void> = async () => Promise.resolve();
  let waitForSuccessfulReviewInboxResponse: () => Promise<void> = async () => Promise.resolve();

  try {
    electronApp = await test.step("launch the packaged Linux executable", async () =>
      electron.launch({
        executablePath: packagedAppPath,
        cwd: path.dirname(packagedAppPath),
        env: {
          ...Object.fromEntries(
            Object.entries(process.env).filter(
              (entry): entry is [string, string] => typeof entry[1] === "string",
            ),
          ),
          DESKTOP_ALLOW_RENDERER_DEBUG_TOOLS: "1",
          HOME: smokeHomeDirectory,
          XDG_CONFIG_HOME: path.join(smokeHomeDirectory, ".config"),
        },
      }),
    );
    const launchedElectronApp = electronApp;
    const apiProxyController = await proxyApiRequests(launchedElectronApp.context());
    disposeApiProxy = apiProxyController.dispose;
    waitForSuccessfulHealthCheck = apiProxyController.waitForSuccessfulHealthCheck;
    waitForSuccessfulReviewInboxResponse = apiProxyController.waitForSuccessfulReviewInboxResponse;

    const page = await test.step("open the first desktop window", async () => {
      const firstWindow = await waitForFirstWindow(launchedElectronApp);
      await firstWindow.waitForLoadState("domcontentloaded");
      return firstWindow;
    });

    await test.step("sign in with the seeded dev identity", async () => {
      await expect(page).toHaveTitle(/AI Value Studio/);
      await expect(page.getByText("LOCAL DEVELOPMENT — AUTH DISABLED")).toBeVisible();
      await page.evaluate(() => {
        window.dispatchEvent(new Event("online"));
      });
      await waitForSuccessfulHealthCheck();
      await expect(page.getByText(/^API inaccessible$|^API unreachable$/)).toHaveCount(0);
      await page.getByLabel(authLabels.localIdentifier).fill("workspace-admin");
      await page.getByLabel(authLabels.displayName).fill("Local Workspace Admin");
      await page.getByRole("button", { name: authLabels.selectIdentity }).click();
    });

    await test.step("open the seeded workspace", async () => {
      const workspaceRow = page.getByRole("row").filter({ hasText: "Local Development Workspace" });
      await expect(workspaceRow).toBeVisible();
      await workspaceRow.getByRole("link", { name: authLabels.openWorkspace }).click();

      await expect(page).toHaveURL(/app:\/\/studio\/studio\/workspace\?workspaceId=/);
      await expect(page.getByRole("heading", { name: "Local Development Workspace" })).toBeVisible();
      await waitForSuccessfulReviewInboxResponse();
    });

    await test.step("verify the secure desktop bridge runtime", async () => {
      const bridgeInfo = await page.evaluate(() => {
        const globalWindow = window as Window & {
          avsDesktop?: {
            isDesktop?: boolean;
            publicConfig?: {
              authMode?: string;
              apiBaseUrl?: string;
            };
          };
          process?: unknown;
        };
        return {
          hasBridge: Boolean(globalWindow.avsDesktop?.isDesktop),
          authMode: globalWindow.avsDesktop?.publicConfig?.authMode ?? null,
          apiBaseUrl: globalWindow.avsDesktop?.publicConfig?.apiBaseUrl ?? null,
          hasNode: typeof globalWindow.process !== "undefined",
        };
      });

      expect(bridgeInfo.hasBridge).toBe(true);
      expect(bridgeInfo.authMode).toBe("dev");
      expect(bridgeInfo.apiBaseUrl).toBe(backendUrl);
      expect(bridgeInfo.hasNode).toBe(false);
    });
  } finally {
    await disposeApiProxy(async () => {
      await closeElectronApp(electronApp);
    });
    fs.rmSync(desktopConfigPath, { force: true });
    fs.rmSync(smokeHomeDirectory, { recursive: true, force: true });
  }
});
