import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

type DevRole = "Consultant" | "WorkspaceAdmin" | "Sponsor" | "Contributor";

const screenshots = {
  home: "test-results/studio-home.png",
  workspace: "test-results/studio-workspace.png",
  program: "test-results/studio-program.png",
  useCase: "test-results/studio-use-case.png",
  members: "test-results/studio-members.png",
} as const;

const labels = {
  programName: /Nom du programme|Program name/,
  strategicObjective: /Objectif stratégique|Strategic objective/,
  createProgram: /Créer le programme|Create program/,
  useCaseTitle: /Titre|Title/,
  department: /Département|Department/,
  owner: /Propriétaire|Owner/,
  recommendation: /Recommandation|Recommendation/,
  createUseCase: /Créer le cas d’usage|Create use case/,
  contributorToAssign: /Contributeur à affecter|Contributor to assign/,
  backToProgram: /Retour au programme|Back to program/,
  backToWorkspace: /Retour à l’espace|Back to workspace/,
  programNotFound: /Programme introuvable|Program not found/,
  useCaseNotFound: /Cas d’usage introuvable|Use case not found/,
} as const;

async function selectDevIdentity(
  page: Page,
  {
    subjectId,
    displayName,
    role,
  }: {
    subjectId: string;
    displayName: string;
    role: DevRole;
  },
) {
  await page.goto("/studio");
  await expect(page.getByLabel("Identifiant local")).toBeVisible();
  await page.getByLabel("Identifiant local").fill(subjectId);
  await page.getByLabel("Nom affiché").fill(displayName);
  await page.getByLabel("Rôle").selectOption(role);
  await page.getByRole("button", { name: "Sélectionner l’identité" }).click();
}

async function storeDevIdentity(
  page: Page,
  request: APIRequestContext,
  {
    subjectId,
    displayName,
    role,
  }: {
    subjectId: string;
    displayName: string;
    role: DevRole;
  },
) {
  const response = await request.post("http://127.0.0.1:8010/api/v1/dev/identity", {
    data: {
      subject_id: subjectId,
      display_name: displayName,
      role,
    },
  });
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as {
    display_name: string;
    headers: Record<string, string>;
    oid: string;
  };

  await page.evaluate((storedIdentity) => {
    window.localStorage.setItem("avs.dev.identity", JSON.stringify(storedIdentity));
  }, {
    subjectId: payload.oid,
    displayName: payload.display_name,
    role,
    headers: payload.headers,
  });
}

async function proxyApiRequests(page: Page, request: APIRequestContext) {
  await page.route("**/api/v1/**", async (route) => {
    const browserRequest = route.request();
    const url = new URL(browserRequest.url());
    const response = await request.fetch(`http://127.0.0.1:8010${url.pathname}${url.search}`, {
      method: browserRequest.method(),
      headers: browserRequest.headers(),
      data: browserRequest.postDataBuffer() ?? undefined,
    });
    await route.fulfill({ response });
  });
}

async function expectNoBlockingAxeViolations(page: Page) {
  const accessibilityScan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const blockingViolations = accessibilityScan.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );
  expect(blockingViolations).toEqual([]);
}

async function capture(page: Page, path: string) {
  await page.screenshot({ path, fullPage: true });
}

test("runs the real backend lifecycle and enforces sponsor/contributor visibility", async ({ page, request }) => {
  await proxyApiRequests(page, request);

  await selectDevIdentity(page, {
    subjectId: "consultant",
    displayName: "Local Consultant",
    role: "Consultant",
  });

  await expect(page.getByRole("heading", { name: "Piloter les espaces, programmes et cas d’usage" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Créer un espace de travail" })).toBeVisible();
  await expectNoBlockingAxeViolations(page);
  await capture(page, screenshots.home);

  const createdWorkspaceName = `Atelier Playwright ${Date.now()}`;
  const createdProgramName = "Programme parcours consultant";
  const createdUseCaseTitle = "Cas d’usage parcours consultant";
  const workspaceDialog = page.locator("dialog[open]");

  await page.getByRole("button", { name: "Créer un espace de travail" }).click();
  await expect(workspaceDialog).toBeVisible();
  await workspaceDialog.getByLabel("Nom").fill(createdWorkspaceName);
  await workspaceDialog
    .getByLabel("Description")
    .fill("Espace créé intégralement depuis l’interface Consultant.");
  await workspaceDialog.getByRole("button", { name: "Créer" }).click();

  await expect(page).toHaveURL(/\/studio\/workspace\?/);
  await expect(page.getByRole("heading", { name: createdWorkspaceName })).toBeVisible();
  const createdWorkspaceUrl = new URL(page.url());
  const createdWorkspaceId = createdWorkspaceUrl.searchParams.get("workspaceId");
  expect(createdWorkspaceId).not.toBeNull();

  await expectNoBlockingAxeViolations(page);
  await capture(page, screenshots.workspace);

  await page.getByLabel(labels.programName).fill(createdProgramName);
  await page.getByLabel(labels.strategicObjective).fill("Cadrer le pipeline de décision pour les cas d’usage IA.");
  await page.getByRole("button", { name: labels.createProgram }).click();

  await expect(page).toHaveURL(/\/studio\/program\?/);
  await expect(page.getByRole("heading", { name: createdProgramName })).toBeVisible();
  const createdProgramUrl = new URL(page.url());
  const createdProgramId = createdProgramUrl.searchParams.get("programId");
  expect(createdProgramId).not.toBeNull();

  await expectNoBlockingAxeViolations(page);
  await capture(page, screenshots.program);

  await page.getByLabel(labels.useCaseTitle).fill(createdUseCaseTitle);
  await page.getByLabel(labels.department).fill("Conseil");
  await page.getByLabel(labels.recommendation).fill("Valider la valeur métier avant la priorisation.");
  await page.getByRole("button", { name: labels.createUseCase }).click();

  await expect(page).toHaveURL(/\/studio\/use-case\?/);
  await expect(page.getByRole("heading", { name: createdUseCaseTitle })).toBeVisible();
  const createdUseCaseUrl = new URL(page.url());
  const createdUseCaseId = createdUseCaseUrl.searchParams.get("useCaseId");
  expect(createdUseCaseId).not.toBeNull();

  await expectNoBlockingAxeViolations(page);
  await capture(page, screenshots.useCase);

  await storeDevIdentity(page, request, {
    subjectId: "workspace-admin",
    displayName: "Local Workspace Admin",
    role: "WorkspaceAdmin",
  });
  await page.goto("/studio");

  const seededWorkspaceRow = page.getByRole("row").filter({ hasText: "Local Development Workspace" });
  await expect(seededWorkspaceRow).toBeVisible();
  await seededWorkspaceRow.getByRole("link", { name: "Ouvrir" }).click();
  await expect(page).toHaveURL(/\/studio\/workspace\?/);
  const seededWorkspaceUrl = new URL(page.url());
  const seededWorkspaceId = seededWorkspaceUrl.searchParams.get("workspaceId");
  expect(seededWorkspaceId).not.toBeNull();

  const sponsorProgramName = "Programme sponsor visible";
  const hiddenProgramName = "Programme masqué sponsor";
  const visibleUseCaseTitle = "Cas visible contributeur";
  const hiddenUseCaseTitle = "Cas masqué contributeur";

  await page.getByLabel(labels.programName).fill(sponsorProgramName);
  await page.getByLabel(labels.strategicObjective).fill("Programme visible pour le sponsor assigné.");
  await page.getByRole("combobox", { name: /^Sponsor$/ }).selectOption({ label: "Local Sponsor" });
  await page.getByRole("combobox", { name: /^Consultant$/ }).selectOption({ label: "Local Consultant" });
  await page.getByRole("button", { name: labels.createProgram }).click();

  await expect(page).toHaveURL(/\/studio\/program\?/);
  const sponsorProgramUrl = new URL(page.url());
  const sponsorProgramId = sponsorProgramUrl.searchParams.get("programId");
  expect(sponsorProgramId).not.toBeNull();

  await page.getByLabel(labels.contributorToAssign).selectOption({ label: "Local Contributor" });

  await page.getByLabel(labels.useCaseTitle).fill(visibleUseCaseTitle);
  await page.getByLabel(labels.department).fill("Opérations");
  await page.getByRole("combobox", { name: labels.owner }).selectOption({ label: "Local Contributor" });
  await page.getByLabel(labels.recommendation).fill("Confier ce cas d’usage au contributor assigné.");
  await page.getByRole("button", { name: labels.createUseCase }).click();

  await expect(page).toHaveURL(/\/studio\/use-case\?/);
  const visibleUseCaseUrl = new URL(page.url());
  const visibleUseCaseId = visibleUseCaseUrl.searchParams.get("useCaseId");
  expect(visibleUseCaseId).not.toBeNull();

  await page.getByRole("link", { name: labels.backToProgram }).click();
  await expect(page).toHaveURL(new RegExp(`program\\?workspaceId=${seededWorkspaceId}&programId=${sponsorProgramId}`));

  await page.getByLabel(labels.useCaseTitle).fill(hiddenUseCaseTitle);
  await page.getByLabel(labels.department).fill("Finance");
  await page.getByLabel(labels.recommendation).fill("Cas non attribué au contributor local.");
  await page.getByRole("button", { name: labels.createUseCase }).click();

  await expect(page).toHaveURL(/\/studio\/use-case\?/);
  const hiddenUseCaseUrl = new URL(page.url());
  const hiddenUseCaseId = hiddenUseCaseUrl.searchParams.get("useCaseId");
  expect(hiddenUseCaseId).not.toBeNull();

  await page.getByRole("link", { name: labels.backToWorkspace }).click();
  await expect(page).toHaveURL(new RegExp(`workspace\\?workspaceId=${seededWorkspaceId}`));

  await page.getByLabel(labels.programName).fill(hiddenProgramName);
  await page.getByLabel(labels.strategicObjective).fill("Programme non visible pour le sponsor local.");
  await page.getByRole("button", { name: labels.createProgram }).click();

  await expect(page).toHaveURL(/\/studio\/program\?/);
  const hiddenProgramUrl = new URL(page.url());
  const hiddenProgramId = hiddenProgramUrl.searchParams.get("programId");
  expect(hiddenProgramId).not.toBeNull();

  await page.goto(`/studio/admin/members?workspaceId=${seededWorkspaceId}`);
  await expect(page.getByText("Local Sponsor")).toBeVisible();
  await expect(page.getByText("Local Contributor")).toBeVisible();
  await expectNoBlockingAxeViolations(page);
  await capture(page, screenshots.members);

  await storeDevIdentity(page, request, {
    subjectId: "sponsor",
    displayName: "Local Sponsor",
    role: "Sponsor",
  });

  await page.goto(`/studio/workspace?workspaceId=${seededWorkspaceId}`);
  await expect(page.getByText(sponsorProgramName)).toBeVisible();
  await expect(page.getByText(hiddenProgramName)).not.toBeVisible();

  await page.goto(`/studio/program?workspaceId=${seededWorkspaceId}&programId=${sponsorProgramId}`);
  await expect(page.getByRole("heading", { name: sponsorProgramName })).toBeVisible();
  await expect(page.getByText(visibleUseCaseTitle)).toBeVisible();
  await expect(page.getByText(hiddenUseCaseTitle)).toBeVisible();

  await page.goto(`/studio/program?workspaceId=${seededWorkspaceId}&programId=${hiddenProgramId}`);
  await expect(page.getByText(labels.programNotFound)).toBeVisible();

  await storeDevIdentity(page, request, {
    subjectId: "contributor",
    displayName: "Local Contributor",
    role: "Contributor",
  });

  await page.goto(`/studio/program?workspaceId=${seededWorkspaceId}&programId=${sponsorProgramId}`);
  await expect(page.getByRole("heading", { name: sponsorProgramName })).toBeVisible();
  await expect(page.getByText(visibleUseCaseTitle)).toBeVisible();
  await expect(page.getByText(hiddenUseCaseTitle)).not.toBeVisible();

  await page.goto(
    `/studio/use-case?workspaceId=${seededWorkspaceId}&programId=${sponsorProgramId}&useCaseId=${visibleUseCaseId}`,
  );
  await expect(page.getByRole("heading", { name: visibleUseCaseTitle })).toBeVisible();

  await page.goto(
    `/studio/use-case?workspaceId=${seededWorkspaceId}&programId=${sponsorProgramId}&useCaseId=${hiddenUseCaseId}`,
  );
  await expect(page.getByText(labels.useCaseNotFound)).toBeVisible();
});
