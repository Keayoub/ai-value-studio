import fs from "node:fs";
import path from "node:path";

import { safeStorage } from "electron";
import type { ICachePlugin, TokenCacheContext } from "@azure/msal-node";

type SerializedEnvelope = {
  encrypted: boolean;
  value: string;
};

function readEnvelope(filePath: string): SerializedEnvelope | null {
  if (!fs.existsSync(filePath)) {
    return null;
  }

  const raw = fs.readFileSync(filePath, "utf8");
  return JSON.parse(raw) as SerializedEnvelope;
}

function writeEnvelope(filePath: string, envelope: SerializedEnvelope) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(envelope), { mode: 0o600 });
}

export function createEncryptedTokenCache(cachePath: string): ICachePlugin {
  return {
    beforeCacheAccess: (tokenCacheContext: TokenCacheContext) => {
      const envelope = readEnvelope(cachePath);
      if (!envelope) {
        return Promise.resolve();
      }

      if (!safeStorage.isEncryptionAvailable()) {
        return Promise.resolve();
      }

      const serialized = envelope.encrypted
        ? safeStorage.decryptString(Buffer.from(envelope.value, "base64"))
        : envelope.value;

      tokenCacheContext.tokenCache.deserialize(serialized);
      return Promise.resolve();
    },
    afterCacheAccess: (tokenCacheContext: TokenCacheContext) => {
      if (!tokenCacheContext.cacheHasChanged) {
        return Promise.resolve();
      }

      if (!safeStorage.isEncryptionAvailable()) {
        return Promise.resolve();
      }

      const serialized = tokenCacheContext.tokenCache.serialize();
      const envelope = {
        encrypted: true,
        value: safeStorage.encryptString(serialized).toString("base64"),
      };

      writeEnvelope(cachePath, envelope);
      return Promise.resolve();
    },
  };
}
