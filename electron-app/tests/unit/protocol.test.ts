import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import {
  buildCsp,
  normalizeRequestPath,
  resolveAsset,
  walkRendererRoot,
} from "../../src/main/protocol";

const scratchRoot = path.resolve(process.cwd(), "test-results", "unit-scratch");

function createScratchDir(prefix: string) {
  fs.mkdirSync(scratchRoot, { recursive: true });
  return fs.mkdtempSync(path.join(scratchRoot, `${prefix}-`));
}

test("normalizes safe paths and rejects traversal", () => {
  assert.equal(normalizeRequestPath("/studio/workspace"), "/studio/workspace");
  assert.throws(() => normalizeRequestPath("/studio/%2e%2e/secrets"), /traversal/i);
});

test("resolves exported routes and injects the studio base href", () => {
  const rendererRoot = createScratchDir("renderer");
  fs.mkdirSync(path.join(rendererRoot, "studio"), { recursive: true });
  fs.writeFileSync(path.join(rendererRoot, "studio.html"), "<html><head></head><body>studio</body></html>");
  fs.writeFileSync(path.join(rendererRoot, "studio", "workspace.html"), "<html><head></head><body>workspace</body></html>");

  const asset = resolveAsset(
    rendererRoot,
    new Set(["studio.html", "studio/workspace.html"]),
    "app://studio/studio/workspace?workspaceId=abc",
  );

  assert.equal(asset.kind, "html");
  assert.equal(asset.filePath.endsWith(path.join("studio", "workspace.html")), true);
  assert.equal(asset.body.includes('<base href="app://studio/">'), true);
});

test("rejects symlinked files that escape the renderer root", { skip: process.platform === "win32" }, () => {
  const rendererRoot = createScratchDir("renderer-symlink-file");
  const outsideRoot = createScratchDir("renderer-outside");
  fs.writeFileSync(path.join(outsideRoot, "secret.txt"), "secret");
  fs.symlinkSync(path.join(outsideRoot, "secret.txt"), path.join(rendererRoot, "secret.txt"));

  assert.throws(
    () =>
      resolveAsset(
        rendererRoot,
        new Set(["secret.txt"]),
        "app://studio/secret.txt",
      ),
    /symbolic links are not allowed/i,
  );
});

test("rejects symlinked directories that escape the renderer root", { skip: process.platform === "win32" }, () => {
  const rendererRoot = createScratchDir("renderer-symlink-dir");
  const outsideRoot = createScratchDir("renderer-dir-outside");
  fs.mkdirSync(path.join(outsideRoot, "nested"), { recursive: true });
  fs.writeFileSync(path.join(outsideRoot, "nested", "workspace.html"), "<html><head></head><body>escape</body></html>");
  fs.symlinkSync(path.join(outsideRoot, "nested"), path.join(rendererRoot, "studio"));

  assert.deepEqual(Array.from(walkRendererRoot(rendererRoot)), []);
});

test("builds a strict CSP with per-page script hashes and API connect-src", () => {
  const html = [
    "<html><head>",
    "<script>window.__inline = true;</script>",
    "<style>body{background:black}</style>",
    "</head><body></body></html>",
  ].join("");

  const csp = buildCsp(html, "https://api.example.com/v1");

  assert.match(csp, /script-src 'self' 'sha256-/);
  assert.match(csp, /style-src 'self' 'sha256-/);
  assert.match(csp, /connect-src 'self' https:\/\/api\.example\.com/);
  assert.match(csp, /frame-ancestors 'none'/);
});
