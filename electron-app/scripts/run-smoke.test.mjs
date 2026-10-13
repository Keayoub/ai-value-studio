import assert from "node:assert/strict";
import test from "node:test";

import { resolveSmokeExecutionPlan } from "./run-smoke.mjs";

test("uses xvfb on Linux CI even when DISPLAY is set", () => {
  const executionPlan = resolveSmokeExecutionPlan({
    env: {
      CI: "true",
      DISPLAY: ":99",
    },
    platform: "linux",
    xvfbRunAvailable: true,
  });

  assert.deepEqual(executionPlan, {
    args: ["-a", "--server-args=-screen 0 1280x720x24", "npm", "run", "smoke:runner"],
    command: "xvfb-run",
    diagnostics: 'Smoke launcher: platform=linux ci=true display=":99" wayland=unset xvfb=available mode=xvfb',
    mode: "xvfb",
  });
});

test("runs directly on Linux when not in CI and a display server is configured", () => {
  const executionPlan = resolveSmokeExecutionPlan({
    env: {
      DISPLAY: ":0",
    },
    platform: "linux",
    xvfbRunAvailable: true,
  });

  assert.deepEqual(executionPlan, {
    args: ["run", "smoke:runner"],
    command: "npm",
    diagnostics: 'Smoke launcher: platform=linux ci=false display=":0" wayland=unset xvfb=available mode=direct',
    mode: "direct",
  });
});

test("uses xvfb on Linux when headless outside CI and xvfb is available", () => {
  const executionPlan = resolveSmokeExecutionPlan({
    env: {},
    platform: "linux",
    xvfbRunAvailable: true,
  });

  assert.deepEqual(executionPlan, {
    args: ["-a", "--server-args=-screen 0 1280x720x24", "npm", "run", "smoke:runner"],
    command: "xvfb-run",
    diagnostics: "Smoke launcher: platform=linux ci=false display=unset wayland=unset xvfb=available mode=xvfb",
    mode: "xvfb",
  });
});

test("fails loudly on Linux CI when xvfb-run is unavailable", () => {
  const executionPlan = resolveSmokeExecutionPlan({
    env: {
      CI: "true",
      DISPLAY: ":99",
    },
    platform: "linux",
    xvfbRunAvailable: false,
  });

  assert.deepEqual(executionPlan, {
    diagnostics: 'Smoke launcher: platform=linux ci=true display=":99" wayland=unset xvfb=missing mode=error',
    error: "Electron smoke test requires xvfb-run on Linux CI runners, but it is not available.",
    mode: "error",
  });
});

test("skips outside CI when Linux has no display server and xvfb-run is unavailable", () => {
  const executionPlan = resolveSmokeExecutionPlan({
    env: {},
    platform: "linux",
    xvfbRunAvailable: false,
  });

  assert.deepEqual(executionPlan, {
    diagnostics: "Smoke launcher: platform=linux ci=false display=unset wayland=unset xvfb=missing mode=skip",
    message: "Skipping Electron smoke test because no display server or xvfb-run is available.",
    mode: "skip",
  });
});
