import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const DEFAULT_DEV_API_BASE_URL = "http://127.0.0.1:8000/api/v1";

/**
 * @param {string | undefined} value
 */
function parseAuthMode(value) {
  return value === "entra" ? "entra" : "dev";
}

/**
 * @param {string} name
 * @param {string | undefined} value
 */
function resolveRequiredValue(name, value) {
  const resolved = value?.trim() ?? "";
  if (!resolved) {
    throw new Error(`Missing ${name} for desktop renderer metadata.`);
  }
  return resolved;
}

/**
 * @param {Record<string, string | undefined>} environment
 * @param {"dev" | "entra"} authMode
 */
function resolveApiBaseUrl(environment, authMode) {
  if (authMode === "entra") {
    return resolveRequiredValue(
      "NEXT_PUBLIC_API_BASE_URL",
      environment.NEXT_PUBLIC_API_BASE_URL ?? environment.NEXT_PUBLIC_API_URL,
    );
  }

  return (
    environment.NEXT_PUBLIC_API_BASE_URL ??
    environment.NEXT_PUBLIC_API_URL ??
    DEFAULT_DEV_API_BASE_URL
  ).trim();
}

/**
 * @param {Record<string, string | undefined>} environment
 * @param {"dev" | "entra"} authMode
 */
function resolveEntraConfig(environment, authMode) {
  const entra = {
    clientId: environment.NEXT_PUBLIC_ENTRA_CLIENT_ID?.trim() ?? "",
    tenantId: environment.NEXT_PUBLIC_ENTRA_TENANT_ID?.trim() ?? "",
    scope: environment.NEXT_PUBLIC_API_SCOPE?.trim() ?? "",
  };

  if (authMode === "entra") {
    return {
      clientId: resolveRequiredValue("NEXT_PUBLIC_ENTRA_CLIENT_ID", entra.clientId),
      tenantId: resolveRequiredValue("NEXT_PUBLIC_ENTRA_TENANT_ID", entra.tenantId),
      scope: resolveRequiredValue("NEXT_PUBLIC_API_SCOPE", entra.scope),
    };
  }

  return entra;
}

/**
 * @param {Record<string, string | undefined>} [environment]
 */
function resolvePublicRuntimeConfig(environment = process.env) {
  const authMode = parseAuthMode(environment.NEXT_PUBLIC_AUTH_MODE);
  return {
    authMode,
    apiBaseUrl: resolveApiBaseUrl(environment, authMode),
    entra: resolveEntraConfig(environment, authMode),
  };
}

/**
 * @param {{
 *   authMode: "dev" | "entra";
 *   apiBaseUrl: string;
 *   entra: { clientId: string; tenantId: string; scope: string };
 * }} runtimeConfig
 * @param {string} [outputPath]
 */
function writePublicRuntimeFile(
  runtimeConfig,
  outputPath = path.join(import.meta.dirname, "..", "out", "desktop-public-build.json"),
) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(runtimeConfig, null, 2)}\n`, "utf8");
}

function isExecutedDirectly() {
  return Boolean(process.argv[1]) && pathToFileURL(process.argv[1]).href === import.meta.url;
}

function main() {
  writePublicRuntimeFile(resolvePublicRuntimeConfig(process.env));
}

if (isExecutedDirectly()) {
  main();
}

export {
  DEFAULT_DEV_API_BASE_URL,
  main,
  parseAuthMode,
  resolveApiBaseUrl,
  resolveEntraConfig,
  resolvePublicRuntimeConfig,
  resolveRequiredValue,
  writePublicRuntimeFile,
};
