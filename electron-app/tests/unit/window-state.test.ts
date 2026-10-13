import assert from "node:assert/strict";
import test from "node:test";

import { sanitizeWindowState } from "../../src/main/window-state";

test("falls back to defaults when bounds are too small", () => {
  const state = sanitizeWindowState({
    width: 200,
    height: 100,
    isMaximized: false,
  });

  assert.equal(state.width, 1440);
  assert.equal(state.height, 960);
  assert.equal(state.isMaximized, false);
});

test("preserves valid bounds", () => {
  const state = sanitizeWindowState({
    width: 1280,
    height: 840,
    x: 40,
    y: 20,
    isMaximized: true,
  });

  assert.deepEqual(state, {
    width: 1280,
    height: 840,
    x: 40,
    y: 20,
    isMaximized: true,
  });
});
