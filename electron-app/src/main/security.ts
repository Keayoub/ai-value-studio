import { shell } from "electron";
import type { BrowserWindow } from "electron";

import { isTrustedStudioFrameUrl } from "./navigation";

type SecurityOptions = {
  allowRendererDebugTools: boolean;
  isPackaged: boolean;
  isAllowedExternalNavigation: (candidateUrl: string) => boolean;
};

function shouldLockDownRendererDebugTools(options: Pick<SecurityOptions, "allowRendererDebugTools" | "isPackaged">) {
  return options.isPackaged && !options.allowRendererDebugTools;
}

export function hardenBrowserWindow(browserWindow: BrowserWindow, options: SecurityOptions) {
  const { webContents } = browserWindow;
  const session = webContents.session;

  session.setPermissionRequestHandler((_contents, _permission, callback) => {
    callback(false);
  });

  session.setPermissionCheckHandler(() => false);

  webContents.setWindowOpenHandler(({ url }) => {
    if (options.isAllowedExternalNavigation(url)) {
      void shell.openExternal(url);
    }

    return { action: "deny" };
  });

  webContents.on("will-attach-webview", (event) => {
    event.preventDefault();
  });

  webContents.on("will-navigate", (event, url) => {
    if (isTrustedStudioFrameUrl(url)) {
      return;
    }

    event.preventDefault();
    if (options.isAllowedExternalNavigation(url)) {
      void shell.openExternal(url);
    }
  });

  if (shouldLockDownRendererDebugTools(options)) {
    webContents.on("devtools-opened", () => {
      webContents.closeDevTools();
    });
  }
}

export { shouldLockDownRendererDebugTools };
