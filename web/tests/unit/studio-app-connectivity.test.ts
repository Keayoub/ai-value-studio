import assert from "node:assert/strict";
import test from "node:test";

import {
  classifyDesktopApiReachability,
  deriveDesktopHealthEndpoint,
  resolveDesktopConnectivityState,
} from "../../src/features/studio/studio-app";

test("desktop health endpoint uses the API origin root", () => {
  assert.equal(
    deriveDesktopHealthEndpoint("https://api.example.com/api/v1"),
    "https://api.example.com/health",
  );
  assert.equal(
    deriveDesktopHealthEndpoint("http://127.0.0.1:8010/api/v1/"),
    "http://127.0.0.1:8010/health",
  );
});

test("desktop API reachability keeps 401 reachable but flags non-health responses as unreachable", () => {
  assert.equal(classifyDesktopApiReachability(200), "reachable");
  assert.equal(classifyDesktopApiReachability(401), "reachable");
  assert.equal(classifyDesktopApiReachability(404), "unreachable");
  assert.equal(classifyDesktopApiReachability(503), "unreachable");
});

test("desktop connectivity state never claims the device is online when navigator is offline", () => {
  assert.deepEqual(
    resolveDesktopConnectivityState({
      isOnline: false,
      reachability: "reachable",
      healthOrigin: "https://api.example.com",
    }),
    {
      kind: "offline",
      healthOrigin: "https://api.example.com",
    },
  );

  assert.deepEqual(
    resolveDesktopConnectivityState({
      isOnline: true,
      reachability: "unreachable",
      healthOrigin: "https://api.example.com",
    }),
    {
      kind: "unreachable",
      healthOrigin: "https://api.example.com",
    },
  );
});
