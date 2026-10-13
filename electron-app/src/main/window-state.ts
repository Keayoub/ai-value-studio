import fs from "node:fs";
import path from "node:path";

import type { App, BrowserWindow, Rectangle } from "electron";

type WindowState = {
  width: number;
  height: number;
  x?: number;
  y?: number;
  isMaximized: boolean;
};

const defaultState: WindowState = {
  width: 1440,
  height: 960,
  isMaximized: false,
};

function sanitizeWindowState(candidate: Partial<WindowState> | null): WindowState {
  if (!candidate) {
    return defaultState;
  }

  const width =
    typeof candidate.width === "number" && Number.isFinite(candidate.width) && candidate.width >= 1200
      ? candidate.width
      : defaultState.width;
  const height =
    typeof candidate.height === "number" && Number.isFinite(candidate.height) && candidate.height >= 800
      ? candidate.height
      : defaultState.height;

  return {
    width,
    height,
    x: typeof candidate.x === "number" && Number.isFinite(candidate.x) ? candidate.x : undefined,
    y: typeof candidate.y === "number" && Number.isFinite(candidate.y) ? candidate.y : undefined,
    isMaximized: candidate.isMaximized === true,
  };
}

export function createWindowStateController(appInstance: App) {
  const statePath = path.join(appInstance.getPath("userData"), "window-state.json");

  function readState() {
    try {
      const content = fs.readFileSync(statePath, "utf8");
      return sanitizeWindowState(JSON.parse(content) as Partial<WindowState>);
    } catch {
      return defaultState;
    }
  }

  function writeState(nextState: WindowState) {
    fs.mkdirSync(path.dirname(statePath), { recursive: true });
    fs.writeFileSync(statePath, JSON.stringify(nextState, null, 2), { mode: 0o600 });
  }

  const loadedState = readState();

  return {
    getBounds(): Rectangle {
      const bounds: Rectangle = {
        width: loadedState.width,
        height: loadedState.height,
        x: 0,
        y: 0,
      };
      if (typeof loadedState.x === "number") {
        bounds.x = loadedState.x;
      }
      if (typeof loadedState.y === "number") {
        bounds.y = loadedState.y;
      }
      return bounds;
    },
    track(browserWindow: BrowserWindow) {
      const persist = () => {
        const bounds = browserWindow.getBounds();
        writeState({
          width: bounds.width,
          height: bounds.height,
          x: bounds.x,
          y: bounds.y,
          isMaximized: browserWindow.isMaximized(),
        });
      };

      if (loadedState.isMaximized) {
        browserWindow.maximize();
      }

      browserWindow.on("close", persist);
    },
  };
}

export { sanitizeWindowState };
