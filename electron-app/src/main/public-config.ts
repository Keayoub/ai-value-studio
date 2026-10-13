import type { DesktopPublicRuntimeConfig } from "../shared/desktop-bridge";

type RendererBuildConfig = DesktopPublicRuntimeConfig;

function parseAuthMode(value: string) {
  if (value === "dev" || value === "entra") {
    return value;
  }

  throw new Error(`Invalid authMode ${JSON.stringify(value)}.`);
}

function resolveRequiredValue(name: string, value: string | undefined) {
  const resolved = value?.trim();
  if (!resolved) {
    throw new Error(`Missing required environment value ${name}.`);
  }
  return resolved;
}

function assertAbsoluteHttpUrl(name: string, value: string) {
  const parsed = new URL(value);
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error(`${name} must use http or https.`);
  }
  if (parsed.username || parsed.password) {
    throw new Error(`${name} must not contain embedded credentials.`);
  }
  if (parsed.search || parsed.hash) {
    throw new Error(`${name} must not contain query or fragment components.`);
  }

  return parsed.toString();
}

function parseDesktopPublicConfig(source: string, candidate: unknown): DesktopPublicRuntimeConfig {
  if (!candidate || typeof candidate !== "object") {
    throw new Error(`${source} must be a JSON object.`);
  }

  const record = candidate as Record<string, unknown>;
  if (typeof record.authMode !== "string") {
    throw new Error(`${source} is missing a valid authMode.`);
  }

  const entraRecord =
    record.entra && typeof record.entra === "object"
      ? (record.entra as Record<string, unknown>)
      : {};

  const config = {
    authMode: parseAuthMode(record.authMode.trim()),
    apiBaseUrl: assertAbsoluteHttpUrl(
      `${source}.apiBaseUrl`,
      resolveRequiredValue(
        `${source}.apiBaseUrl`,
        typeof record.apiBaseUrl === "string" ? record.apiBaseUrl : undefined,
      ),
    ),
    entra: {
      clientId:
        typeof entraRecord.clientId === "string" ? entraRecord.clientId.trim() : "",
      tenantId:
        typeof entraRecord.tenantId === "string" ? entraRecord.tenantId.trim() : "",
      scope: typeof entraRecord.scope === "string" ? entraRecord.scope.trim() : "",
    },
  } satisfies DesktopPublicRuntimeConfig;

  if (config.authMode === "entra") {
    if (!config.entra.clientId || !config.entra.tenantId || !config.entra.scope) {
      throw new Error(`${source} must include Entra clientId, tenantId, and scope in entra mode.`);
    }
  }

  return config;
}

function assertRendererBuildCompatibility(
  rendererConfig: RendererBuildConfig,
  publicConfig: DesktopPublicRuntimeConfig,
) {
  if (rendererConfig.authMode !== publicConfig.authMode) {
    throw new Error(
      `Desktop public config authMode ${JSON.stringify(publicConfig.authMode)} does not match renderer build authMode ${JSON.stringify(rendererConfig.authMode)}.`,
    );
  }

  if (new URL(rendererConfig.apiBaseUrl).origin !== new URL(publicConfig.apiBaseUrl).origin) {
    throw new Error(
      "Desktop public config apiBaseUrl origin does not match the packaged renderer build.",
    );
  }
}

export {
  assertAbsoluteHttpUrl,
  assertRendererBuildCompatibility,
  parseAuthMode,
  parseDesktopPublicConfig,
  resolveRequiredValue,
};
