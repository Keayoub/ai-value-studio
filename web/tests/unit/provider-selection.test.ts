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
