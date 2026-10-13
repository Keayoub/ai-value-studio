import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import type { Protocol } from "electron";

const contentTypes = new Map<string, string>([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".ico", "image/x-icon"],
  [".js", "application/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".md", "text/markdown; charset=utf-8"],
  [".png", "image/png"],
  [".svg", "image/svg+xml; charset=utf-8"],
  [".txt", "text/plain; charset=utf-8"],
  [".woff2", "font/woff2"],
]);

type ProtocolRegistrationOptions = {
  session: Protocol;
  rendererRoot: string;
  apiBaseUrl: string;
};

type ResolvedAsset =
  | {
      kind: "html";
      filePath: string;
      body: string;
    }
  | {
      kind: "file";
      filePath: string;
      body: Buffer;
    };

function hashInlineBlocks(html: string, tagName: "script" | "style") {
  const pattern = new RegExp(`<${tagName}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${tagName}>`, "gi");
  const hashes: string[] = [];

  let match = pattern.exec(html);
  while (match) {
    const raw = match[0];
    if (!/\ssrc=/.test(raw)) {
      hashes.push(
        `'sha256-${crypto.createHash("sha256").update(match[1] ?? "").digest("base64")}'`,
      );
    }
    match = pattern.exec(html);
  }

  return hashes;
}

function buildCsp(html: string, apiBaseUrl: string) {
  const scriptHashes = hashInlineBlocks(html, "script");
  const styleHashes = hashInlineBlocks(html, "style");
  const connectSources = new Set(["'self'", new URL(apiBaseUrl).origin]);

  return [
    "default-src 'self'",
    `script-src 'self' ${scriptHashes.join(" ")}`.trim(),
    `style-src 'self' ${styleHashes.join(" ")}`.trim(),
    "img-src 'self' data: blob:",
    "font-src 'self'",
    `connect-src ${Array.from(connectSources).join(" ")}`,
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
    "form-action 'none'",
    "frame-src 'none'",
    "worker-src 'self'",
  ].join("; ");
}

function assertWithinRoot(rendererRoot: string, candidatePath: string) {
  const relative = path.relative(rendererRoot, candidatePath);
  if (relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative))) {
    return;
  }

  throw new Error("Asset escapes renderer root.");
}

function walkRendererRoot(rendererRoot: string) {
  const knownFiles = new Set<string>();
  const canonicalRoot = fs.realpathSync.native(rendererRoot);
  const visitedDirectories = new Set<string>([canonicalRoot]);

  const stack = [{ realPath: canonicalRoot, relativePath: "" }];
  while (stack.length > 0) {
    const current = stack.pop();
    if (!current) {
      continue;
    }

    const entries = fs.readdirSync(current.realPath, { withFileTypes: true });
    for (const entry of entries) {
      const absolute = path.join(current.realPath, entry.name);
      const relativePath = current.relativePath
        ? path.posix.join(current.relativePath, entry.name)
        : entry.name;

      if (entry.isSymbolicLink()) {
        continue;
      }

      if (entry.isDirectory()) {
        const nextRealPath = fs.realpathSync.native(absolute);
        assertWithinRoot(canonicalRoot, nextRealPath);
        if (visitedDirectories.has(nextRealPath)) {
          continue;
        }
        visitedDirectories.add(nextRealPath);
        stack.push({ realPath: nextRealPath, relativePath });
        continue;
      }

      const realFilePath = fs.realpathSync.native(absolute);
      assertWithinRoot(canonicalRoot, realFilePath);
      knownFiles.add(relativePath);
    }
  }

  return knownFiles;
}

function normalizeRequestPath(candidatePath: string) {
  const decoded = decodeURIComponent(candidatePath);
  if (decoded.includes("\0")) {
    throw new Error("Invalid path.");
  }

  if (decoded.split("/").includes("..")) {
    throw new Error("Path traversal is not allowed.");
  }

  const normalized = path.posix.normalize(decoded);
  if (!normalized.startsWith("/")) {
    throw new Error("Invalid path.");
  }

  if (normalized.split("/").includes("..")) {
    throw new Error("Path traversal is not allowed.");
  }

  return normalized;
}

function injectBaseHref(html: string) {
  return html.replace("<head>", '<head><base href="app://studio/">');
}

function resolveAsset(rendererRoot: string, knownFiles: Set<string>, candidateUrl: string): ResolvedAsset {
  const canonicalRoot = fs.realpathSync.native(rendererRoot);
  const parsedUrl = new URL(candidateUrl);
  if (parsedUrl.host !== "studio") {
    throw new Error("Unknown app host.");
  }

  const normalized = normalizeRequestPath(parsedUrl.pathname);
  const relativePath = normalized.replace(/^\/+/, "");
  const candidates =
    relativePath === ""
      ? ["index.html"]
      : [
          relativePath,
          `${relativePath}.html`,
          `${relativePath}/index.html`,
        ];

  const matched = candidates.find((candidate) => knownFiles.has(candidate));
  if (!matched) {
    throw new Error("Unknown route.");
  }

  const filePath = path.join(rendererRoot, matched);
  const stats = fs.lstatSync(filePath);
  if (stats.isSymbolicLink()) {
    throw new Error("Symbolic links are not allowed.");
  }

  const realFilePath = fs.realpathSync.native(filePath);
  assertWithinRoot(canonicalRoot, realFilePath);
  if (path.extname(filePath) === ".html") {
    return {
      kind: "html",
      filePath,
      body: injectBaseHref(fs.readFileSync(filePath, "utf8")),
    };
  }

  return {
    kind: "file",
    filePath,
    body: fs.readFileSync(filePath),
  };
}

function contentTypeFor(filePath: string) {
  return contentTypes.get(path.extname(filePath)) ?? "application/octet-stream";
}

export function registerStudioProtocol(options: ProtocolRegistrationOptions) {
  const knownFiles = walkRendererRoot(options.rendererRoot);

  options.session.handle("app", (request) => {
    try {
      const asset = resolveAsset(options.rendererRoot, knownFiles, request.url);
      if (asset.kind === "html") {
        return new Response(asset.body, {
          headers: {
            "Content-Security-Policy": buildCsp(asset.body, options.apiBaseUrl),
            "Content-Type": contentTypeFor(asset.filePath),
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
          },
        });
      }

      return new Response(new Uint8Array(asset.body), {
        headers: {
          "Content-Type": contentTypeFor(asset.filePath),
          "Cross-Origin-Resource-Policy": "same-origin",
          "X-Content-Type-Options": "nosniff",
        },
      });
    } catch (error) {
      return new Response(error instanceof Error ? error.message : "Not found", {
        status: error instanceof Error && error.message === "Unknown route." ? 404 : 400,
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }
  });
}

export { buildCsp, normalizeRequestPath, resolveAsset, walkRendererRoot };
