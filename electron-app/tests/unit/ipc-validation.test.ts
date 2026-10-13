import assert from "node:assert/strict";
import test from "node:test";

import { assertSaveDocumentPayload, sanitizeSuggestedName } from "../../src/main/ipc-validation";

test("sanitizes a safe document name", () => {
  assert.equal(sanitizeSuggestedName("brief.pdf"), "brief.pdf");
});

test("rejects path traversal names", () => {
  assert.throws(() => sanitizeSuggestedName("../brief.pdf"), /Invalid suggested file name/);
});

test("accepts valid save payloads", () => {
  const payload = assertSaveDocumentPayload({
    suggestedName: "brief.pdf",
    contentType: "application/pdf",
    bytes: new Uint8Array([1, 2, 3]),
  });

  assert.equal(payload.suggestedName, "brief.pdf");
  assert.equal(payload.contentType, "application/pdf");
  assert.deepEqual(Array.from(payload.bytes), [1, 2, 3]);
});

test("rejects invalid save payload bytes", () => {
  assert.throws(
    () =>
      assertSaveDocumentPayload({
        suggestedName: "brief.pdf",
        contentType: "application/pdf",
        bytes: [1, 2, 3],
      }),
    /Invalid save-document payload bytes/,
  );
});
