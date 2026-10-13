import test from "node:test";
import assert from "node:assert/strict";

import { getPublicRuntimeConfig, parseAuthMode } from "../../src/features/auth/runtime";

test("parseAuthMode defaults to dev", () => {
  assert.equal(parseAuthMode(undefined), "dev");
  assert.equal(parseAuthMode("unexpected"), "dev");
  assert.equal(parseAuthMode("entra"), "entra");
});

test("getPublicRuntimeConfig resolves public auth settings", () => {
  const config = getPublicRuntimeConfig({
    NEXT_PUBLIC_AUTH_MODE: "entra",
    NEXT_PUBLIC_API_BASE_URL: "https://api.example.test/api/v1",
    NEXT_PUBLIC_ENTRA_CLIENT_ID: "client-id",
    NEXT_PUBLIC_ENTRA_TENANT_ID: "tenant-id",
    NEXT_PUBLIC_API_SCOPE: "api://scope/access_as_user",
  });

  assert.equal(config.authMode, "entra");
  assert.equal(config.apiBaseUrl, "https://api.example.test/api/v1");
  assert.equal(config.entra.clientId, "client-id");
  assert.equal(config.entra.tenantId, "tenant-id");
  assert.equal(config.entra.scope, "api://scope/access_as_user");
});

test("getPublicRuntimeConfig keeps the dev API fallback when no public URL is configured", () => {
  const config = getPublicRuntimeConfig({});

  assert.equal(config.authMode, "dev");
  assert.equal(config.apiBaseUrl, "http://127.0.0.1:8000/api/v1");
  assert.equal(config.entra.clientId, "");
  assert.equal(config.entra.tenantId, "");
  assert.equal(config.entra.scope, "");
});

test("getPublicRuntimeConfig prefers desktop bridge config when available", () => {
  const previousDescriptor = Object.getOwnPropertyDescriptor(globalThis, "window");
  const nextWindow = {
    avsDesktop: {
      isDesktop: true,
      publicConfig: {
        authMode: "dev",
        apiBaseUrl: "http://127.0.0.1:8010/api/v1",
        entra: {
          clientId: "",
          tenantId: "",
          scope: "",
        },
      },
      app: {
        getVersion: async () => "1.0.0",
      },
      auth: {
        getState: async () => ({ status: "unauthenticated", account: null }),
        signIn: async () => ({ status: "unauthenticated", account: null }),
        signOut: async () => ({ status: "unauthenticated", account: null }),
        getAccessToken: async () => "",
      },
      documents: {
        save: async () => ({ canceled: true, filePath: null }),
      },
    },
  } as unknown as Window;

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    writable: true,
    value: nextWindow,
  });

  try {
    const config = getPublicRuntimeConfig({
      NEXT_PUBLIC_AUTH_MODE: "entra",
      NEXT_PUBLIC_API_BASE_URL: "https://api.example.test/api/v1",
      NEXT_PUBLIC_ENTRA_CLIENT_ID: "client-id",
      NEXT_PUBLIC_ENTRA_TENANT_ID: "tenant-id",
      NEXT_PUBLIC_API_SCOPE: "api://scope/access_as_user",
    });

    assert.equal(config.authMode, "dev");
    assert.equal(config.apiBaseUrl, "http://127.0.0.1:8010/api/v1");
  } finally {
    if (previousDescriptor) {
      Object.defineProperty(globalThis, "window", previousDescriptor);
      return;
    }

    delete (globalThis as { window?: Window }).window;
  }
});
