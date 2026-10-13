import assert from "node:assert/strict";
import test from "node:test";

import { getReleaseBuildEnv } from "./package-release.mjs";

test("accepts explicit placeholder Entra public release settings", () => {
  const env = {
    NEXT_PUBLIC_AUTH_MODE: "entra",
    NEXT_PUBLIC_API_BASE_URL: "https://api.example.com/api/v1",
    NEXT_PUBLIC_ENTRA_CLIENT_ID: "00000000-0000-0000-0000-000000000000",
    NEXT_PUBLIC_ENTRA_TENANT_ID: "common",
    NEXT_PUBLIC_API_SCOPE: "api://avs-api/access_as_user",
  };

  assert.equal(getReleaseBuildEnv(env), env);
});

test("rejects release packaging unless auth mode is explicitly entra", () => {
  assert.throws(
    () =>
      getReleaseBuildEnv({
        NEXT_PUBLIC_API_BASE_URL: "https://api.example.com/api/v1",
        NEXT_PUBLIC_ENTRA_CLIENT_ID: "client-id",
        NEXT_PUBLIC_ENTRA_TENANT_ID: "tenant-id",
        NEXT_PUBLIC_API_SCOPE: "api://scope/access_as_user",
      }),
    /NEXT_PUBLIC_AUTH_MODE/i,
  );

  assert.throws(
    () =>
      getReleaseBuildEnv({
        NEXT_PUBLIC_AUTH_MODE: "dev",
        NEXT_PUBLIC_API_BASE_URL: "https://api.example.com/api/v1",
        NEXT_PUBLIC_ENTRA_CLIENT_ID: "client-id",
        NEXT_PUBLIC_ENTRA_TENANT_ID: "tenant-id",
        NEXT_PUBLIC_API_SCOPE: "api://scope/access_as_user",
      }),
    /=entra/i,
  );
});

test("rejects missing or invalid explicit release endpoints and Entra settings", () => {
  assert.throws(
    () =>
      getReleaseBuildEnv({
        NEXT_PUBLIC_AUTH_MODE: "entra",
        NEXT_PUBLIC_API_BASE_URL: "https://api.example.com/api/v1?debug=1",
        NEXT_PUBLIC_ENTRA_CLIENT_ID: "client-id",
        NEXT_PUBLIC_ENTRA_TENANT_ID: "tenant-id",
        NEXT_PUBLIC_API_SCOPE: "api://scope/access_as_user",
      }),
    /query string or fragment/i,
  );

  assert.throws(
    () =>
      getReleaseBuildEnv({
        NEXT_PUBLIC_AUTH_MODE: "entra",
        NEXT_PUBLIC_API_BASE_URL: "https://api.example.com/api/v1",
        NEXT_PUBLIC_ENTRA_CLIENT_ID: "client-id",
        NEXT_PUBLIC_ENTRA_TENANT_ID: "",
        NEXT_PUBLIC_API_SCOPE: "api://scope/access_as_user",
      }),
    /NEXT_PUBLIC_ENTRA_TENANT_ID/i,
  );
});
