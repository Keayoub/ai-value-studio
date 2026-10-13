import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const xvfbRunArgs = ["-a", "--server-args=-screen 0 1280x720x24"];

function formatEnvValue(value) {
  return value ? JSON.stringify(value) : "unset";
}

export function resolveSmokeExecutionPlan({
  env = process.env,
  platform = process.platform,
  xvfbRunAvailable,
}) {
  const hasDisplay = Boolean(env.DISPLAY || env.WAYLAND_DISPLAY);
  const isCi = Boolean(env.CI);

  if (platform !== "linux") {
    return {
      args: ["run", "smoke:runner"],
      command: "npm",
      diagnostics: `Smoke launcher: platform=${platform} ci=${isCi} mode=direct`,
      mode: "direct",
    };
  }

  const diagnosticsPrefix =
    `Smoke launcher: platform=linux ci=${isCi} display=${formatEnvValue(env.DISPLAY)} ` +
    `wayland=${formatEnvValue(env.WAYLAND_DISPLAY)} xvfb=${xvfbRunAvailable ? "available" : "missing"}`;

  if (isCi) {
    if (!xvfbRunAvailable) {
      return {
        diagnostics: `${diagnosticsPrefix} mode=error`,
        error: "Electron smoke test requires xvfb-run on Linux CI runners, but it is not available.",
        mode: "error",
      };
    }

    return {
      args: [...xvfbRunArgs, "npm", "run", "smoke:runner"],
      command: "xvfb-run",
      diagnostics: `${diagnosticsPrefix} mode=xvfb`,
      mode: "xvfb",
    };
  }

  if (hasDisplay) {
    return {
      args: ["run", "smoke:runner"],
      command: "npm",
      diagnostics: `${diagnosticsPrefix} mode=direct`,
      mode: "direct",
    };
  }

  if (xvfbRunAvailable) {
    return {
      args: [...xvfbRunArgs, "npm", "run", "smoke:runner"],
      command: "xvfb-run",
      diagnostics: `${diagnosticsPrefix} mode=xvfb`,
      mode: "xvfb",
    };
  }

  return {
    diagnostics: `${diagnosticsPrefix} mode=skip`,
    message: "Skipping Electron smoke test because no display server or xvfb-run is available.",
    mode: "skip",
  };
}

function probeXvfbRun(commandRunner = spawnSync, env = process.env) {
  const probe = commandRunner("xvfb-run", ["--help"], {
    env,
    stdio: "ignore",
  });

  return probe.status === 0;
}

function run(command, args, commandRunner = spawnSync, env = process.env) {
  const result = commandRunner(command, args, {
    env,
    stdio: "inherit",
  });

  if (typeof result.status === "number") {
    process.exit(result.status);
  }

  throw result.error ?? new Error(`Failed to run ${command}`);
}

export function main({
  commandRunner = spawnSync,
  env = process.env,
  platform = process.platform,
  stdout = process.stdout,
} = {}) {
  const xvfbRunAvailable =
    platform === "linux" ? probeXvfbRun(commandRunner, env) : false;
  const executionPlan = resolveSmokeExecutionPlan({
    env,
    platform,
    xvfbRunAvailable,
  });

  stdout.write(`${executionPlan.diagnostics}\n`);

  if (executionPlan.mode === "skip") {
    stdout.write(`${executionPlan.message}\n`);
    process.exit(0);
  }

  if (executionPlan.mode === "error") {
    throw new Error(executionPlan.error);
  }

  run(executionPlan.command, executionPlan.args, commandRunner, env);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
