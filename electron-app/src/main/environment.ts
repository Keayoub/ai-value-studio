import fs from "node:fs";
import path from "node:path";

import { app } from "electron";

import type { DesktopPublicRuntimeConfig } from "../shared/desktop-bridge";
import {
  assertRendererBuildCompatibility,
  parseAuthMode,
  parseDesktopPublicConfig,
} from "./public-config";

export type DesktopEnvironment = {
  apiBaseUrl: string;
  allowedExternalOrigins: string[];
  allowRendererDebugTools: boolean;
  iconPath: string;
  preloadPath: string;
  rendererRoot: string;
  publicConfig: DesktopPublicRuntimeConfig;
  entra:
    | {
        clientId: string;
        tenantId: string;
        apiScope: string;
      }
    | null;
};

function readRendererBuildConfig(rendererRoot: string) {
  const filePath = path.join(rendererRoot, "desktop-public-build.json");
  if (!fs.existsSync(filePath)) {
    throw new Error(
      `Missing renderer build metadata at ${filePath}. Rebuild web/out before packaging the desktop app.`,
    );
  }

  return parseDesktopPublicConfig(
    filePath,
    JSON.parse(fs.readFileSync(filePath, "utf8")) as unknown,
  );
}

function readPackagedPublicConfig() {
  const configPath = path.join(path.dirname(process.execPath), "desktop-public.json");
  if (!fs.existsSync(configPath)) {
    throw new Error(
      `Missing required desktop public config ${configPath}. Create it from desktop-public.template.json before launching the packaged app.`,
    );
  }

  return parseDesktopPublicConfig(
    configPath,
    JSON.parse(fs.readFileSync(configPath, "utf8")) as unknown,
  );
}

function readAllowedOrigins(environment: NodeJS.ProcessEnv, publicConfig: DesktopPublicRuntimeConfig) {
  const configured = (environment.DESKTOP_ALLOWED_EXTERNAL_ORIGINS ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  const defaults = [new URL(publicConfig.apiBaseUrl).origin];
  if (publicConfig.authMode === "entra") {
    defaults.push("https://login.microsoftonline.com");
  }

  return [...new Set([...defaults, ...configured])];
}

function readEnvironmentPublicConfig(environment: NodeJS.ProcessEnv) {
  const authMode = parseAuthMode(
    environment.NEXT_PUBLIC_AUTH_MODE?.trim() === "entra" ? "entra" : "dev",
  );
  return parseDesktopPublicConfig("process.env", {
    authMode,
    apiBaseUrl:
      environment.NEXT_PUBLIC_API_BASE_URL ?? environment.NEXT_PUBLIC_API_URL,
    entra: {
      clientId:
        environment.DESKTOP_ENTRA_CLIENT_ID ?? environment.NEXT_PUBLIC_ENTRA_CLIENT_ID ?? "",
      tenantId:
        environment.DESKTOP_ENTRA_TENANT_ID ?? environment.NEXT_PUBLIC_ENTRA_TENANT_ID ?? "",
      scope: environment.DESKTOP_API_SCOPE ?? environment.NEXT_PUBLIC_API_SCOPE ?? "",
    },
  });
}

function shouldAllowRendererDebugTools(
  environment: { DESKTOP_ALLOW_RENDERER_DEBUG_TOOLS?: string },
  publicConfig: Pick<DesktopPublicRuntimeConfig, "authMode">,
) {
  return (
    environment.DESKTOP_ALLOW_RENDERER_DEBUG_TOOLS === "1" &&
    publicConfig.authMode === "dev"
  );
}

export function readDesktopEnvironment(environment: NodeJS.ProcessEnv): DesktopEnvironment {
  const appRoot = app.getAppPath();
  const rendererRoot = app.isPackaged
    ? path.join(process.resourcesPath, "renderer")
    : path.resolve(appRoot, "..", "web", "out");
  const publicConfig = app.isPackaged
    ? (() => {
        const packagedPublicConfig = readPackagedPublicConfig();
        assertRendererBuildCompatibility(
          readRendererBuildConfig(rendererRoot),
          packagedPublicConfig,
        );
        return packagedPublicConfig;
      })()
    : readEnvironmentPublicConfig(environment);

  return {
    apiBaseUrl: publicConfig.apiBaseUrl,
    allowedExternalOrigins: readAllowedOrigins(environment, publicConfig),
    allowRendererDebugTools: shouldAllowRendererDebugTools(environment, publicConfig),
    iconPath: path.join(appRoot, "assets", "icon.png"),
    preloadPath: path.join(appRoot, "dist", "preload.js"),
    rendererRoot,
    publicConfig,
    entra:
      publicConfig.authMode === "entra"
        ? {
            clientId: publicConfig.entra.clientId,
            tenantId: publicConfig.entra.tenantId,
            apiScope: publicConfig.entra.scope,
          }
        : null,
  };
}

export { shouldAllowRendererDebugTools };
