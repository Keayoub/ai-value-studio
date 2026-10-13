import { app, BrowserWindow, Menu, protocol } from "electron";
import electronSquirrelStartup from "electron-squirrel-startup";

import { createDesktopAuthService } from "./main/auth-service";
import { readDesktopEnvironment } from "./main/environment";
import { registerDesktopIpc } from "./main/ipc";
import { buildApplicationMenu } from "./main/menu";
import { isAllowedExternalNavigation } from "./main/navigation";
import { registerStudioProtocol } from "./main/protocol";
import { hardenBrowserWindow } from "./main/security";
import { createWindowStateController } from "./main/window-state";

if (electronSquirrelStartup) {
  app.quit();
}

const hasSingleInstanceLock = app.requestSingleInstanceLock();
if (!hasSingleInstanceLock) {
  app.quit();
}

protocol.registerSchemesAsPrivileged([
  {
    scheme: "app",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
      corsEnabled: false,
      allowServiceWorkers: false,
    },
  },
]);

const environment = hasSingleInstanceLock ? readDesktopEnvironment(process.env) : null;
let mainWindow: BrowserWindow | null = null;

function createMainWindow() {
  if (!environment) {
    throw new Error("Desktop environment is unavailable without the single-instance lock.");
  }

  const windowState = createWindowStateController(app);
  const browserWindow = new BrowserWindow({
    ...windowState.getBounds(),
    minWidth: 1200,
    minHeight: 800,
    show: false,
    autoHideMenuBar: false,
    title: "AI Value Studio Desktop",
    backgroundColor: "#f6f7fb",
    icon: environment.iconPath,
    webPreferences: {
      preload: environment.preloadPath,
      additionalArguments: [
        `--avs-desktop-public-config=${Buffer.from(
          JSON.stringify(environment.publicConfig),
          "utf8",
        ).toString("base64")}`,
      ],
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      webSecurity: true,
      allowRunningInsecureContent: false,
      devTools: !app.isPackaged || environment.allowRendererDebugTools,
    },
  });

  hardenBrowserWindow(browserWindow, {
    allowRendererDebugTools: environment.allowRendererDebugTools,
    isPackaged: app.isPackaged,
    isAllowedExternalNavigation: (candidateUrl) =>
      isAllowedExternalNavigation(candidateUrl, environment.allowedExternalOrigins),
  });

  windowState.track(browserWindow);

  browserWindow.once("ready-to-show", () => {
    browserWindow.show();
  });

  void browserWindow.loadURL("app://studio/studio");

  browserWindow.on("closed", () => {
    if (mainWindow === browserWindow) {
      mainWindow = null;
    }
  });

  return browserWindow;
}

void app.whenReady().then(() => {
  if (!environment) {
    return;
  }

  registerStudioProtocol({
    session: protocol,
    rendererRoot: environment.rendererRoot,
    apiBaseUrl: environment.apiBaseUrl,
  });

  const authService = createDesktopAuthService(environment);

  mainWindow = createMainWindow();
  registerDesktopIpc({
    authService,
    getMainWindow: () => mainWindow,
    appVersion: app.getVersion(),
  });

  Menu.setApplicationMenu(buildApplicationMenu(() => mainWindow));
}).catch((error: unknown) => {
  console.error("Failed to initialize AI Value Studio Desktop.", error);
  app.quit();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (mainWindow === null) {
    mainWindow = createMainWindow();
  }
});

app.on("second-instance", () => {
  if (!mainWindow) {
    return;
  }

  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }

  mainWindow.focus();
});
