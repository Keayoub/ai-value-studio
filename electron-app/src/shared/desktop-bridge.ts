export type DesktopAuthState = {
  status: "authenticated" | "unauthenticated";
  account: {
    homeAccountId: string;
    username: string;
    name: string | null;
  } | null;
};

export type DesktopPublicRuntimeConfig = {
  authMode: "dev" | "entra";
  apiBaseUrl: string;
  entra: {
    clientId: string;
    tenantId: string;
    scope: string;
  };
};

export type SaveDocumentPayload = {
  suggestedName: string;
  contentType: string;
  bytes: Uint8Array;
};

export type SaveDocumentResult =
  | {
      canceled: true;
      filePath: null;
    }
  | {
      canceled: false;
      filePath: string;
    };

export type DesktopBridge = {
  isDesktop: true;
  publicConfig: DesktopPublicRuntimeConfig;
  app: {
    getVersion: () => Promise<string>;
  };
  auth: {
    getState: () => Promise<DesktopAuthState>;
    signIn: () => Promise<DesktopAuthState>;
    signOut: () => Promise<DesktopAuthState>;
    getAccessToken: () => Promise<string>;
  };
  documents: {
    save: (payload: SaveDocumentPayload) => Promise<SaveDocumentResult>;
  };
};
