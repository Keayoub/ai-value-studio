import assert from "node:assert/strict";
import test from "node:test";

import { closeWithCleanup } from "../helpers/close-with-cleanup";

test("runs cleanup after a successful close", async () => {
  const steps: string[] = [];

  await closeWithCleanup(
    () => {
      steps.push("close");
      return Promise.resolve();
    },
    () => {
      steps.push("cleanup");
      return Promise.resolve();
    },
    "cleanup failed",
  );

  assert.deepEqual(steps, ["close", "cleanup"]);
});

test("runs cleanup and rethrows the original close error when cleanup succeeds", async () => {
  const steps: string[] = [];
  const closeError = new Error("close failed");

  await assert.rejects(
    closeWithCleanup(
      () => {
        steps.push("close");
        return Promise.reject(closeError);
      },
      () => {
        steps.push("cleanup");
        return Promise.resolve();
      },
      "cleanup failed",
    ),
    (error: unknown) => {
      assert.equal(error, closeError);
      return true;
    },
  );

  assert.deepEqual(steps, ["close", "cleanup"]);
});

test("rethrows the cleanup error when close succeeds", async () => {
  const cleanupError = new Error("cleanup failed");

  await assert.rejects(
    closeWithCleanup(
      () => Promise.resolve(),
      () => Promise.reject(cleanupError),
      "cleanup failed",
    ),
    (error: unknown) => {
      assert.equal(error, cleanupError);
      return true;
    },
  );
});

test("surfaces both close and cleanup failures", async () => {
  const closeError = new Error("close failed");
  const cleanupError = new Error("cleanup failed");

  await assert.rejects(
    closeWithCleanup(
      () => Promise.reject(closeError),
      () => Promise.reject(cleanupError),
      "combined failure",
    ),
    (error: unknown) => {
      assert.ok(error instanceof AggregateError);
      assert.equal(error.message, "combined failure");
      assert.deepEqual(error.errors, [closeError, cleanupError]);
      return true;
    },
  );
});
