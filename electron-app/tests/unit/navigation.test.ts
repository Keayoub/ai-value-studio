import assert from "node:assert/strict";
import test from "node:test";

import {
  isAllowedExternalNavigation,
  isTrustedStudioFrameUrl,
  isTrustedStudioRoutePath,
} from "../../src/main/navigation";

test("allows only configured external origins", () => {
  assert.equal(
    isAllowedExternalNavigation("https://login.microsoftonline.com/common/oauth2/v2.0/authorize", [
      "https://login.microsoftonline.com",
      "https://api.example.com",
    ]),
    true,
  );
  assert.equal(
    isAllowedExternalNavigation("https://evil.example.com", ["https://login.microsoftonline.com"]),
    false,
  );
  assert.equal(
    isAllowedExternalNavigation("file:///tmp/payload.html", ["https://login.microsoftonline.com"]),
    false,
  );
});

test("trusts only app studio frame urls", () => {
  assert.equal(isTrustedStudioFrameUrl("app://studio/studio"), true);
  assert.equal(isTrustedStudioFrameUrl("app://studio/studio/workspace?workspaceId=abc"), true);
  assert.equal(isTrustedStudioFrameUrl("app://another-host/studio"), false);
  assert.equal(isTrustedStudioFrameUrl("https://studio.example.com"), false);
  assert.equal(isTrustedStudioFrameUrl("app://studio/_next/static/chunks/app.js"), false);
  assert.equal(isTrustedStudioFrameUrl("app://studio/desktop-public-build.json"), false);
});

test("trusts only interactive studio route paths", () => {
  assert.equal(isTrustedStudioRoutePath("/studio"), true);
  assert.equal(isTrustedStudioRoutePath("/studio/use-case"), true);
  assert.equal(isTrustedStudioRoutePath("/"), false);
  assert.equal(isTrustedStudioRoutePath("/_next/static/chunks/app.js"), false);
});
