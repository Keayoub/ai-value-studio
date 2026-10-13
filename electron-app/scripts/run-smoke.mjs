import { spawnSync } from "node:child_process";

function run(command, args) {
  const result = spawnSync(command, args, {
    stdio: "inherit",
    env: process.env,
  });

  if (typeof result.status === "number") {
    process.exit(result.status);
  }

  throw result.error ?? new Error(`Failed to run ${command}`);
}

const hasDisplay = Boolean(process.env.DISPLAY || process.env.WAYLAND_DISPLAY);

if (process.platform === "linux" && !hasDisplay) {
  const probe = spawnSync("xvfb-run", ["--help"], { stdio: "ignore" });
  if (probe.status === 0) {
    run("xvfb-run", ["-a", "npm", "run", "smoke:runner"]);
  }

  process.stdout.write("Skipping Electron smoke test because no display server or xvfb-run is available.\n");
  process.exit(0);
}

run("npm", ["run", "smoke:runner"]);
