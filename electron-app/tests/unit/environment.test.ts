import assert from "node:assert/strict";
import test from "node:test";

import {
  assertRendererBuildCompatibility,
  parseDesktopPublicConfig,
} from "../../src/main/public-config";
import { shouldAllowRendererDebugTools } from "../../src/main/environment";

test("parses a valid packaged desktop public config", () => {
  const config = parseDesktopPublicConfig("desktop-public.json", {
    authMode: "entra",
    apiBaseUrl: "https://api.example.com/api/v1",
    entra: {
      clientId: "client-id",
      tenantId: "tenant-id",
      scope: "api://scope/access_as_user",
    },
  });

  assert.equal(config.authMode, "entra");
  assert.equal(config.apiBaseUrl, "https://api.example.com/api/v1");
  assert.equal(config.entra.clientId, "client-id");
});

test("rejects invalid packaged desktop public config values", () => {
  assert.throws(
    () =>
      parseDesktopPublicConfig("desktop-public.json", {
        authMode: "unexpected",
        apiBaseUrl: "file:///tmp/api",
        entra: {},
      }),
    /authMode|http or https/i,
  );
});

test("fails closed when packaged desktop config authMode or API origin diverges from the renderer build", () => {
  assert.throws(
    () =>
      assertRendererBuildCompatibility(
        {
          authMode: "entra",
          apiBaseUrl: "https://api.example.com/api/v1",
          entra: {
            clientId: "client-id",
            tenantId: "tenant-id",
            scope: "api://scope/access_as_user",
          },
        },
        {
          authMode: "dev",
          apiBaseUrl: "https://api.example.com/internal",
          entra: {
            clientId: "",
            tenantId: "",
            scope: "",
          },
        },
      ),
    /authMode/i,
  );

  assert.throws(
    () =>
      assertRendererBuildCompatibility(
        {
          authMode: "dev",
          apiBaseUrl: "https://api.example.com/api/v1",
          entra: {
            clientId: "",
            tenantId: "",
            scope: "",
          },
        },
        {
          authMode: "dev",
          apiBaseUrl: "https://other.example.com/api/v1",
          entra: {
            clientId: "",
            tenantId: "",
            scope: "",
          },
        },
      ),
    /origin does not match/i,
  );
});

test("only allows the renderer debugtools test switch for verified dev auth mode", () => {
  assert.equal(
    shouldAllowRendererDebugTools(
      { DESKTOP_ALLOW_RENDERER_DEBUG_TOOLS: "1" },
      { authMode: "dev" },
    ),
    true,
  );

  assert.equal(
    shouldAllowRendererDebugTools(
      { DESKTOP_ALLOW_RENDERER_DEBUG_TOOLS: "1" },
      { authMode: "entra" },
    ),
    false,
  );

  assert.equal(
    shouldAllowRendererDebugTools(
      { DESKTOP_ALLOW_RENDERER_DEBUG_TOOLS: "0" },
      { authMode: "dev" },
    ),
    false,
  );
});
