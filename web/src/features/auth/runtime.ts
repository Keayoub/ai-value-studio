import type { AuthMode } from "@/features/api/types";

export type PublicRuntimeConfig = {
  apiBaseUrl: string;
  authMode: AuthMode;
  entra: {
    clientId: string;
    tenantId: string;
    scope: string;
  };
};

export function getPublicRuntimeConfig(environment: Record<string, string | undefined>): PublicRuntimeConfig {
  const authMode = parseAuthMode(environment.NEXT_PUBLIC_AUTH_MODE);
  return {
    apiBaseUrl: (environment.NEXT_PUBLIC_API_BASE_URL ?? environment.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1").trim(),
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
