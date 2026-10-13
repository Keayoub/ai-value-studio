const fs = require("node:fs");
const path = require("node:path");

const sourceDir = path.resolve(__dirname, "..", "..", "web", "out");
const targetDir = path.resolve(__dirname, "..", "renderer");
const sourceIndex = path.join(sourceDir, "index.html");

if (!fs.existsSync(sourceIndex)) {
  throw new Error(
    `Missing ${sourceIndex}. Build the static web export first with \`cd web && npm run build\`.`,
  );
}

fs.rmSync(targetDir, { recursive: true, force: true });
fs.mkdirSync(targetDir, { recursive: true });
fs.cpSync(sourceDir, targetDir, { recursive: true });

process.stdout.write(`Copied ${sourceDir} -> ${targetDir}\n`);
