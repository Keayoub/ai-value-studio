import assert from "node:assert/strict";
import test from "node:test";

import { localizeSeededDevFixtureName } from "../../src/features/studio/copy.dev";

test("seeded dev fixture labels localize every reviewed French identity and workspace string", () => {
  assert.equal(localizeSeededDevFixtureName("fr", "Local Consultant"), "Consultant local");
  assert.equal(localizeSeededDevFixtureName("fr", "Local Workspace Admin"), "Administrateur local");
  assert.equal(localizeSeededDevFixtureName("fr", "Local Sponsor"), "Sponsor local");
  assert.equal(localizeSeededDevFixtureName("fr", "Local Contributor"), "Contributeur local");
  assert.equal(
    localizeSeededDevFixtureName("fr", "Local Development Workspace"),
    "Espace de développement local",
  );
  assert.equal(
    localizeSeededDevFixtureName("fr", "Seeded local development workspace."),
    "Espace de développement local préconfiguré.",
  );
});

test("seeded dev fixture localization does not translate arbitrary data or English sessions", () => {
  assert.equal(localizeSeededDevFixtureName("en", "Local Sponsor"), "Local Sponsor");
  assert.equal(localizeSeededDevFixtureName("fr", "Programme client"), "Programme client");
  assert.equal(localizeSeededDevFixtureName("fr", null), null);
});
