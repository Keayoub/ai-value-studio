import assert from "node:assert/strict";
import test from "node:test";

import { ApiClientError } from "../../src/features/api/browser-api-client";
import { isPermissionDeniedError } from "../../src/features/studio/data-surface";

test("data surface permission helper only marks 403 problem details as permission denied", () => {
  assert.equal(
    isPermissionDeniedError(
      new ApiClientError({
        type: "about:blank",
        title: "Forbidden",
        status: 403,
        detail: "Forbidden",
        instance: "/test",
        request_id: "test",
      }),
    ),
    true,
  );

  assert.equal(
    isPermissionDeniedError(
      new ApiClientError({
        type: "about:blank",
        title: "Unauthorized",
        status: 401,
        detail: "Unauthorized",
        instance: "/test",
        request_id: "test",
      }),
    ),
    false,
  );

  assert.equal(isPermissionDeniedError(new Error("boom")), false);
});
