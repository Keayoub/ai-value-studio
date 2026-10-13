import fs from "node:fs/promises";
import path from "node:path";

import { dialog, ipcMain } from "electron";
import type { BrowserWindow } from "electron";

import type { SaveDocumentResult } from "../shared/desktop-bridge";
import type { DesktopAuthService } from "./auth-service";
import { assertSaveDocumentPayload } from "./ipc-validation";
import { isTrustedStudioFrameUrl } from "./navigation";

type IpcRegistrationOptions = {
  authService: DesktopAuthService;
  getMainWindow: () => BrowserWindow | null;
  appVersion: string;
};

function assertTrustedFrame(frameUrl: string) {
  if (!isTrustedStudioFrameUrl(frameUrl)) {
    throw new Error(`Rejected IPC call from untrusted frame ${frameUrl}.`);
  }
}

function senderFrameUrl(frame: Electron.WebFrameMain | null) {
  if (!frame) {
    throw new Error("Rejected IPC call without a sender frame.");
  }

  return frame.url;
}

function buildFilters(contentType: string) {
  if (contentType.includes("pdf")) {
    return [{ name: "PDF", extensions: ["pdf"] }];
  }
  if (contentType.includes("markdown")) {
    return [{ name: "Markdown", extensions: ["md"] }];
  }
  if (contentType.startsWith("text/")) {
    return [{ name: "Text", extensions: ["txt"] }];
  }

  return [{ name: "Document", extensions: ["bin"] }];
}

export function registerDesktopIpc(options: IpcRegistrationOptions) {
  ipcMain.handle("desktop:app:get-version", (event) => {
    assertTrustedFrame(senderFrameUrl(event.senderFrame));
    return options.appVersion;
  });

  ipcMain.handle("desktop:auth:get-state", async (event) => {
    assertTrustedFrame(senderFrameUrl(event.senderFrame));
    return await options.authService.getState();
  });

  ipcMain.handle("desktop:auth:sign-in", async (event) => {
    assertTrustedFrame(senderFrameUrl(event.senderFrame));
    return await options.authService.signIn();
  });

  ipcMain.handle("desktop:auth:sign-out", async (event) => {
    assertTrustedFrame(senderFrameUrl(event.senderFrame));
    return await options.authService.signOut();
  });

  ipcMain.handle("desktop:auth:get-access-token", async (event) => {
    assertTrustedFrame(senderFrameUrl(event.senderFrame));
    return await options.authService.getAccessToken();
  });

  ipcMain.handle("desktop:documents:save", async (event, payload): Promise<SaveDocumentResult> => {
    assertTrustedFrame(senderFrameUrl(event.senderFrame));
    const parsedPayload = assertSaveDocumentPayload(payload);
    const browserWindow = options.getMainWindow();

    const response = browserWindow
      ? await dialog.showSaveDialog(browserWindow, {
          defaultPath: parsedPayload.suggestedName,
          buttonLabel: "Enregistrer",
          filters: buildFilters(parsedPayload.contentType),
          showsTagField: false,
          properties: ["createDirectory", "showOverwriteConfirmation"],
        })
      : await dialog.showSaveDialog({
          defaultPath: parsedPayload.suggestedName,
          buttonLabel: "Enregistrer",
          filters: buildFilters(parsedPayload.contentType),
          showsTagField: false,
          properties: ["createDirectory", "showOverwriteConfirmation"],
        });

    if (response.canceled || !response.filePath) {
      return { canceled: true, filePath: null };
    }

    await fs.mkdir(path.dirname(response.filePath), { recursive: true });
    await fs.writeFile(response.filePath, parsedPayload.bytes, { mode: 0o600 });
    return { canceled: false, filePath: response.filePath };
  });
}
