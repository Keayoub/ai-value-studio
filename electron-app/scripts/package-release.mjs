import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const authModeKey = "NEXT_PUBLIC_AUTH_MODE";
const apiBaseUrlKey = "NEXT_PUBLIC_API_BASE_URL";
const entraPublicKeys = [
  "NEXT_PUBLIC_ENTRA_CLIENT_ID",
  "NEXT_PUBLIC_ENTRA_TENANT_ID",
  "NEXT_PUBLIC_API_SCOPE",
];
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";

function readExplicitEnv(env, key) {
  if (!Object.hasOwn(env, key)) {
    throw new Error(`Release packaging requires explicit ${key} in the caller environment.`);
  }

  const value = env[key];
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Release packaging requires non-empty ${key} in the caller environment.`);
  }

  return value.trim();
}

function validateApiBaseUrl(value) {
  const parsedUrl = new URL(value);
  if (!["http:", "https:"].includes(parsedUrl.protocol)) {
    throw new Error(`${apiBaseUrlKey} must be an absolute http or https URL.`);
  }

  if (parsedUrl.username || parsedUrl.password) {
    throw new Error(`${apiBaseUrlKey} must not include embedded credentials.`);
  }

  if (parsedUrl.search || parsedUrl.hash) {
    throw new Error(`${apiBaseUrlKey} must not include a query string or fragment.`);
  }
}

export function getReleaseBuildEnv(env = process.env) {
  const authMode = readExplicitEnv(env, authModeKey);
  if (authMode !== "entra") {
    throw new Error(`Release packaging requires ${authModeKey}=entra.`);
  }

  const apiBaseUrl = readExplicitEnv(env, apiBaseUrlKey);
  validateApiBaseUrl(apiBaseUrl);

  for (const key of entraPublicKeys) {
    readExplicitEnv(env, key);
  }

  return env;
}

function run(command, args, env) {
  const result = spawnSync(command, args, {
    stdio: "inherit",
    env,
  });

  if (typeof result.status === "number") {
    if (result.status !== 0) {
      process.exit(result.status);
    }

    return;
  }

  throw result.error ?? new Error(`Failed to run ${command}`);
}

export function packageRelease(env = process.env) {
  const releaseEnv = getReleaseBuildEnv(env);
  const webRoot = path.resolve(import.meta.dirname, "..", "..", "web");

  run(npmCommand, ["--prefix", webRoot, "run", "build"], releaseEnv);
  run(npmCommand, ["run", "pack"], releaseEnv);
}

const entryPath = process.argv[1] ? path.resolve(process.argv[1]) : "";
if (entryPath === fileURLToPath(import.meta.url)) {
  packageRelease();
}
