import test from "node:test";
import assert from "node:assert/strict";

import {
  formatProgramStatusLabel,
  formatUseCaseStatusLabel,
  formatWorkspaceRoleLabel,
  studioCopyFor,
} from "../../src/features/studio/copy";

test("studio copy defaults to French-first labels", () => {
  const copy = studioCopyFor("fr");

  assert.equal(copy.heroTitle, "Piloter les espaces, programmes et cas d’usage");
  assert.equal(copy.navigation.home, "Connexion et espaces");
  assert.equal(copy.home.createWorkspace, "Créer un espace de travail");
});

test("studio copy exposes localized status and role labels", () => {
  assert.equal(formatProgramStatusLabel("fr", "Decision"), "Décision");
  assert.equal(formatUseCaseStatusLabel("fr", "InProgress"), "En cours");
  assert.equal(formatWorkspaceRoleLabel("fr", "Contributor"), "Contributeur");

  assert.equal(formatProgramStatusLabel("en", "Decision"), "Decision");
  assert.equal(formatUseCaseStatusLabel("en", "InProgress"), "In progress");
  assert.equal(formatWorkspaceRoleLabel("en", "WorkspaceAdmin"), "Workspace admin");
});
