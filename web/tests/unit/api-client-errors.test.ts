import test from "node:test";
import assert from "node:assert/strict";

import { ApiClientError, BrowserApiClient } from "../../src/features/api/browser-api-client";

test("browser api client normalizes RFC7807 errors", async () => {
  const client = new BrowserApiClient("http://example.test/api/v1", async () => ({}));
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        type: "about:blank",
        title: "Forbidden",
        status: 403,
        detail: "Denied",
        instance: "/test",
        request_id: "req-1",
      }),
      {
        status: 403,
        headers: { "Content-Type": "application/json" },
      },
    );

  await assert.rejects(
    () => client.getMe(),
    (error: unknown) => {
      assert.ok(error instanceof ApiClientError);
      assert.equal(error.problem.status, 403);
      assert.equal(error.problem.request_id, "req-1");
      return true;
    },
  );

  globalThis.fetch = originalFetch;
});
