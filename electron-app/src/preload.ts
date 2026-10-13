import { contextBridge, ipcRenderer } from "electron";

import type {
  DesktopAuthState,
  DesktopBridge,
  DesktopPublicRuntimeConfig,
  SaveDocumentPayload,
  SaveDocumentResult,
} from "./shared/desktop-bridge";

async function invoke<T>(channel: string, payload?: unknown): Promise<T> {
  return ipcRenderer.invoke(channel, payload) as Promise<T>;
}

function readPublicConfig() {
  const argumentPrefix = "--avs-desktop-public-config=";
  const encoded = process.argv.find((value) => value.startsWith(argumentPrefix));
  if (!encoded) {
    throw new Error("Missing desktop public runtime configuration.");
  }

  return JSON.parse(
    Buffer.from(encoded.slice(argumentPrefix.length), "base64").toString("utf8"),
  ) as DesktopPublicRuntimeConfig;
}

const desktopBridge: DesktopBridge = {
  isDesktop: true,
  publicConfig: readPublicConfig(),
  app: {
    getVersion: () => invoke<string>("desktop:app:get-version"),
  },
  auth: {
    getState: () => invoke<DesktopAuthState>("desktop:auth:get-state"),
    signIn: () => invoke<DesktopAuthState>("desktop:auth:sign-in"),
    signOut: () => invoke<DesktopAuthState>("desktop:auth:sign-out"),
    getAccessToken: () => invoke<string>("desktop:auth:get-access-token"),
  },
  documents: {
    save: (payload: SaveDocumentPayload) =>
      invoke<SaveDocumentResult>("desktop:documents:save", payload),
  },
};

contextBridge.exposeInMainWorld("avsDesktop", desktopBridge);
