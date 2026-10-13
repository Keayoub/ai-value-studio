import type { AuthMode } from "@/features/api/types";

export type DesktopBridge = {
  isDesktop: true;
  publicConfig: PublicRuntimeConfig;
  app: {
    getVersion: () => Promise<string>;
  };
  auth: {
    getState: () => Promise<{
      status: "authenticated" | "unauthenticated";
      account: {
        homeAccountId: string;
        username: string;
        name: string | null;
      } | null;
    }>;
    signIn: () => Promise<{
      status: "authenticated" | "unauthenticated";
      account: {
        homeAccountId: string;
        username: string;
        name: string | null;
      } | null;
    }>;
    signOut: () => Promise<{
      status: "authenticated" | "unauthenticated";
      account: {
        homeAccountId: string;
        username: string;
        name: string | null;
      } | null;
    }>;
    getAccessToken: () => Promise<string>;
  };
  documents: {
    save: (payload: {
      suggestedName: string;
      contentType: string;
      bytes: Uint8Array;
    }) => Promise<
      | { canceled: true; filePath: null }
      | { canceled: false; filePath: string }
    >;
  };
};

export type PublicRuntimeConfig = {
  apiBaseUrl: string;
  authMode: AuthMode;
  entra: {
    clientId: string;
    tenantId: string;
    scope: string;
  };
};

export function getPublicRuntimeConfig(
  environment: Record<string, string | undefined>,
): PublicRuntimeConfig {
  const desktopBridge = getDesktopBridge();
  if (desktopBridge) {
    return desktopBridge.publicConfig;
  }

  const authMode = parseAuthMode(environment.NEXT_PUBLIC_AUTH_MODE);
  return {
    apiBaseUrl: (
      environment.NEXT_PUBLIC_API_BASE_URL ??
      environment.NEXT_PUBLIC_API_URL ??
      "http://127.0.0.1:8000/api/v1"
    ).trim(),
    authMode,
    entra: {
      clientId: environment.NEXT_PUBLIC_ENTRA_CLIENT_ID?.trim() ?? "",
      tenantId: environment.NEXT_PUBLIC_ENTRA_TENANT_ID?.trim() ?? "",
      scope: environment.NEXT_PUBLIC_API_SCOPE?.trim() ?? "",
    },
  };
}

export function parseAuthMode(value: string | undefined): AuthMode {
  if (value === "entra") {
    return "entra";
  }
  return "dev";
}

export function getDesktopBridge(): DesktopBridge | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.avsDesktop ?? null;
}

export function isDesktopRuntime() {
  return getDesktopBridge() !== null;
}

declare global {
  interface Window {
    avsDesktop?: DesktopBridge;
  }
}
