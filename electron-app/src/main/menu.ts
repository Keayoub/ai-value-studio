import { Menu } from "electron";
import type { BrowserWindow, MenuItemConstructorOptions } from "electron";

export function buildApplicationMenu(getMainWindow: () => BrowserWindow | null) {
  const commonItems: MenuItemConstructorOptions[] = [
    {
      label: "Fichier",
      submenu: [
        {
          label: "Quitter",
          role: "quit",
        },
      ],
    },
    {
      label: "Edition",
      submenu: [
        { role: "undo", label: "Annuler" },
        { role: "redo", label: "Rétablir" },
        { type: "separator" },
        { role: "cut", label: "Couper" },
        { role: "copy", label: "Copier" },
        { role: "paste", label: "Coller" },
        { role: "selectAll", label: "Tout sélectionner" },
      ],
    },
    {
      label: "Affichage",
      submenu: [
        {
          label: "Recharger",
          accelerator: "CmdOrCtrl+R",
          click: () => getMainWindow()?.reload(),
        },
        { role: "resetZoom", label: "Taille réelle" },
        { role: "zoomIn", label: "Zoom avant" },
        { role: "zoomOut", label: "Zoom arrière" },
        { type: "separator" },
        { role: "togglefullscreen", label: "Plein écran" },
      ],
    },
    {
      label: "Fenêtre",
      submenu: [
        { role: "minimize", label: "Réduire" },
        { role: "close", label: "Fermer" },
      ],
    },
  ];

  if (process.platform === "darwin") {
    commonItems.unshift({
      label: "AI Value Studio",
      submenu: [{ role: "about", label: "À propos d’AI Value Studio" }],
    });
  }

  return Menu.buildFromTemplate(commonItems);
}
