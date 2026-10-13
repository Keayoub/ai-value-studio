import assert from "node:assert/strict";
import test from "node:test";

import { shouldLockDownRendererDebugTools } from "../../src/main/security";

test("locks down renderer debug tools for packaged production launches by default", () => {
  assert.equal(
    shouldLockDownRendererDebugTools({
      allowRendererDebugTools: false,
      isPackaged: true,
    }),
    true,
  );
});

test("keeps renderer debug tools available for explicit automation launches", () => {
  assert.equal(
    shouldLockDownRendererDebugTools({
      allowRendererDebugTools: true,
      isPackaged: true,
    }),
    false,
  );
  assert.equal(
    shouldLockDownRendererDebugTools({
      allowRendererDebugTools: false,
      isPackaged: false,
    }),
    false,
  );
});
