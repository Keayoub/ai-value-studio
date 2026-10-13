import assert from "node:assert/strict";
import test from "node:test";

const writePublicRuntimeModulePromise = import("../../scripts/write-public-runtime.mjs");

test("write-public-runtime keeps the dev fallback metadata aligned with an unconfigured dev build", async () => {
  const { DEFAULT_DEV_API_BASE_URL, resolvePublicRuntimeConfig } =
    await writePublicRuntimeModulePromise;

  const config = resolvePublicRuntimeConfig({});

  assert.deepEqual(config, {
    authMode: "dev",
    apiBaseUrl: DEFAULT_DEV_API_BASE_URL,
    entra: {
      clientId: "",
      tenantId: "",
      scope: "",
    },
  });
});

test("write-public-runtime requires explicit Entra metadata for entra builds", async () => {
  const { resolvePublicRuntimeConfig } = await writePublicRuntimeModulePromise;

  assert.throws(
    () =>
      resolvePublicRuntimeConfig({
        NEXT_PUBLIC_AUTH_MODE: "entra",
      }),
    /NEXT_PUBLIC_API_BASE_URL/i,
  );

  assert.throws(
    () =>
      resolvePublicRuntimeConfig({
        NEXT_PUBLIC_AUTH_MODE: "entra",
        NEXT_PUBLIC_API_BASE_URL: "https://api.example.test/api/v1",
      }),
    /NEXT_PUBLIC_ENTRA_CLIENT_ID/i,
  );
});

test("write-public-runtime never relabels a dev build as entra just because entra values are present", async () => {
  const { resolvePublicRuntimeConfig } = await writePublicRuntimeModulePromise;

  const config = resolvePublicRuntimeConfig({
    NEXT_PUBLIC_API_BASE_URL: "https://api.example.test/api/v1",
    NEXT_PUBLIC_ENTRA_CLIENT_ID: "client-id",
    NEXT_PUBLIC_ENTRA_TENANT_ID: "tenant-id",
    NEXT_PUBLIC_API_SCOPE: "api://scope/access_as_user",
  });

  assert.equal(config.authMode, "dev");
  assert.equal(config.apiBaseUrl, "https://api.example.test/api/v1");
  assert.equal(config.entra.clientId, "client-id");
  assert.equal(config.entra.tenantId, "tenant-id");
  assert.equal(config.entra.scope, "api://scope/access_as_user");
});
