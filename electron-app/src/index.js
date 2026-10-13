const fs = require("node:fs");
const path = require("node:path");
const { app, BrowserWindow } = require("electron");

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (require("electron-squirrel-startup")) {
  app.quit();
}

let mainWindow;

function resolveRendererIndexPath() {
  const candidates = app.isPackaged
    ? [
        path.join(process.resourcesPath, "renderer", "index.html"),
        path.join(__dirname, "..", "renderer", "index.html"),
      ]
    : [
        path.join(__dirname, "..", "renderer", "index.html"),
        path.join(__dirname, "..", "..", "web", "out", "index.html"),
      ];

  const rendererIndex = candidates.find((candidate) => fs.existsSync(candidate));
  if (!rendererIndex) {
    throw new Error(
      "Missing exported web renderer. Run `cd web && npm run build` before `cd electron-app && npm start`.",
    );
  }

  return rendererIndex;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1200,
    minHeight: 800,
    autoHideMenuBar: true,
    title: "AI Value Studio Desktop",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      devTools: !app.isPackaged,
    },
  });

  mainWindow.loadFile(resolveRendererIndexPath());

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (mainWindow === null) {
    createWindow();
  }
});
