export async function closeWithCleanup(
  close: () => Promise<void>,
  cleanup: () => Promise<void>,
  cleanupFailureMessage: string,
) {
  let didCloseFail = false;
  let closeError: unknown;

  try {
    await close();
  } catch (error) {
    didCloseFail = true;
    closeError = error;
  }

  try {
    await cleanup();
  } catch (cleanupError) {
    if (!didCloseFail) {
      throw cleanupError;
    }

    throw new AggregateError([closeError, cleanupError], cleanupFailureMessage, {
      cause: cleanupError,
    });
  }

  if (didCloseFail) {
    throw closeError;
  }
}
