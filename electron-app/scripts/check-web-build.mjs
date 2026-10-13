import fs from "node:fs";
import path from "node:path";

const rendererRoot = path.resolve(import.meta.dirname, "..", "..", "web", "out");
const studioHtmlPath = path.join(rendererRoot, "studio.html");
const buildConfigPath = path.join(rendererRoot, "desktop-public-build.json");

if (!fs.existsSync(studioHtmlPath)) {
  throw new Error(
    `Missing ${studioHtmlPath}. Build the static web export first with \`cd web && npm run build\`.`,
  );
}

if (!fs.existsSync(buildConfigPath)) {
  throw new Error(
    `Missing ${buildConfigPath}. Rebuild the static web export so Electron can validate the packaged desktop config.`,
  );
}

const buildConfig = JSON.parse(fs.readFileSync(buildConfigPath, "utf8"));
if (buildConfig?.authMode !== "dev" && buildConfig?.authMode !== "entra") {
  throw new Error(`Invalid authMode in ${buildConfigPath}.`);
}

const parsedApiBaseUrl = new URL(String(buildConfig.apiBaseUrl));
if (!["http:", "https:"].includes(parsedApiBaseUrl.protocol)) {
  throw new Error(`Invalid apiBaseUrl in ${buildConfigPath}; expected http or https.`);
}

if (buildConfig.authMode !== "dev") {
  const inspectedFiles = [
    path.join(rendererRoot, "studio.html"),
    path.join(rendererRoot, "studio", "workspace.html"),
    path.join(rendererRoot, "studio", "program.html"),
    path.join(rendererRoot, "studio", "use-case.html"),
  ].filter((candidate) => fs.existsSync(candidate));

  const forbiddenMarkers = [
    "LOCAL DEVELOPMENT — AUTH DISABLED",
    "Select identity",
    "/dev/identity",
    "Development headers",
  ];

  for (const filePath of inspectedFiles) {
    const content = fs.readFileSync(filePath, "utf8");
    const matchedMarker = forbiddenMarkers.find((marker) => content.includes(marker));
    if (matchedMarker) {
      throw new Error(
        `Release renderer still exposes dev identity marker ${JSON.stringify(matchedMarker)} in ${filePath}. Rebuild web/out with NEXT_PUBLIC_AUTH_MODE=entra.`,
      );
    }
  }
}

process.stdout.write(
  `Verified renderer export at ${rendererRoot} (${buildConfig.authMode}, ${parsedApiBaseUrl.origin})\n`,
);
