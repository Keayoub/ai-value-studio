import type { SaveDocumentPayload } from "../shared/desktop-bridge";

export function sanitizeSuggestedName(candidate: string) {
  const trimmed = candidate.trim();
  if (!trimmed || trimmed.includes("/") || trimmed.includes("\\") || trimmed.includes("\0")) {
    throw new Error("Invalid suggested file name.");
  }

  return trimmed;
}

export function assertSaveDocumentPayload(payload: unknown): SaveDocumentPayload {
  if (
    !payload ||
    typeof payload !== "object" ||
    !("suggestedName" in payload) ||
    !("contentType" in payload) ||
    !("bytes" in payload)
  ) {
    throw new Error("Invalid save-document payload.");
  }

  const { suggestedName, contentType, bytes } = payload as Record<string, unknown>;
  if (typeof suggestedName !== "string" || typeof contentType !== "string") {
    throw new Error("Invalid save-document payload.");
  }

  if (!(bytes instanceof Uint8Array)) {
    throw new Error("Invalid save-document payload bytes.");
  }

  return {
    suggestedName: sanitizeSuggestedName(suggestedName),
    contentType,
    bytes,
  };
}
