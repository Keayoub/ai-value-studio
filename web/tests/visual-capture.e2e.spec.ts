import { mkdir } from "node:fs/promises";
import { join } from "node:path";

import { expect, test, type Locator, type Page } from "@playwright/test";

import {
  bootstrapUseCase,
  completeAndSubmitWizard,
  fetchDevIdentityHeaders,
  fillStepFive,
  fillStepFour,
  fillStepOne,
  fillStepSeven,
  fillStepSix,
  fillStepThree,
  fillStepTwo,
  openUseCase,
  proxyApiRequests,
  saveValueAssessmentAndRecalculateScorecard,
  selectDevIdentity,
  setWorkspaceDefaultLanguage,
  submitReviewAndGenerateBrief,
  type BootstrapResult,
  type ScorecardSnapshot,
  type ValueAssessmentSeed,
} from "./helpers";

const CAPTURE_DIR = process.env.CAPTURE_DIR;
const REVIEW_HEADING = /Revue avant soumission/;
const SCORECARD_TITLE = /Scorecard de valeur et de priorité/;
const DOCUMENT_CENTRE_TITLE = /Centre documentaire/;
const PORTFOLIO_TITLE = /Matrice portefeuille IA/;
const DEV_BANNER =
  /LOCAL DEVELOPMENT — AUTH DISABLED|DÉVELOPPEMENT LOCAL — AUTH DÉSACTIVÉE/;
const EXECUTIVE_BRIEF = /Note exécutive/;
const INSPECT_BVA_DATA = /Voir les données BVA|Inspect BVA data/;
const LOCAL_CONSULTANT_NAME = "Consultant local";
const LOCAL_SPONSOR_NAME = "Sponsor local";
const SEEDED_WORKSPACE_NAME_TRANSLATIONS: Record<string, string> = {
  "Local Development Workspace": "Espace de développement local",
  "Local Demo Workspace": "Espace de démonstration local",
};
const CAPTURE_VIEWPORTS = [
  ["desktop", { width: 1440, height: 900 }],
  ["mobile-320", { width: 320, height: 844 }],
  ["mobile-375", { width: 375, height: 844 }],
  ["mobile-390", { width: 390, height: 844 }],
  ["mobile-430", { width: 430, height: 932 }],
] as const;
type SeededCase = {
  programName: string;
  useCaseTitle: string;
  strategicObjective: string;
  scorecard: ValueAssessmentSeed;
};

function makeScorecardSeed(seed: ValueAssessmentSeed): ValueAssessmentSeed {
  return { currency: "EUR", ...seed };
}

function numberPattern(value: number) {
  const digits = Math.round(value).toString();
  if (digits.length <= 3) {
    return new RegExp(digits);
  }
  return new RegExp(`${digits.slice(0, -3)}[\\s,.  ]?${digits.slice(-3)}`);
}

function localizeSeededWorkspaceName(workspaceName: string) {
  const localizedWorkspaceName = SEEDED_WORKSPACE_NAME_TRANSLATIONS[workspaceName];
  expect(localizedWorkspaceName, `Unexpected seeded workspace fixture name: ${workspaceName}`).toBeTruthy();
  return localizedWorkspaceName ?? workspaceName;
}

async function hideNextDevIndicator(page: Page) {
  await page.evaluate(() => {
    if (document.getElementById("visual-capture-hide-next-dev-indicator")) {
      return;
    }

    const style = document.createElement("style");
    style.id = "visual-capture-hide-next-dev-indicator";
    style.textContent = `
      nextjs-portal,
      [data-nextjs-toast],
      .nextjs-toast,
      .dev-tools-indicator-menu {
        display: none !important;
      }
    `;
    document.head.appendChild(style);
  });
}

const SEEDED_CASES = [
  {
    programName: "Programme Sinistres Auto",
    useCaseTitle: "FNOL auto prioritaire",
    strategicObjective: "Réduire le délai de qualification des sinistres auto complexes.",
    scorecard: makeScorecardSeed({ annual_volume: 18000, time_saved_hours: 0.35, hourly_cost: 52, error_reduction_rate: 18, average_error_cost: 110, revenue_capacity_value: 56000, estimated_annual_cost: 38000, time_to_impact_months: 3, primary_kpi: "Temps moyen de qualification FNOL", kpi_target: "-35%", confidence: "high", override: { dimension: "business_value", score: 5, reason: "Backlog FNOL tendu avec gains déjà validés en atelier opérationnel." } }),
  },
  {
    programName: "Programme Triage Documents",
    useCaseTitle: "Qualification pièces sinistre habitation",
    strategicObjective: "Stabiliser la complétude documentaire avant l'affectation gestionnaire.",
    scorecard: makeScorecardSeed({ annual_volume: 14500, time_saved_hours: 0.28, hourly_cost: 47, error_reduction_rate: 24, average_error_cost: 95, revenue_capacity_value: 34000, estimated_annual_cost: 26000, time_to_impact_months: 4, primary_kpi: "Dossiers complets au premier passage", kpi_target: "+22%", confidence: "medium", override: { dimension: "data_feasibility", score: 4, reason: "GED homogène sur 80% des flux." } }),
  },
  {
    programName: "Programme Estimation",
    useCaseTitle: "Pré-contrôle devis carrosserie",
    strategicObjective: "Accélérer la revue des devis simples avant validation expert.",
    scorecard: makeScorecardSeed({ annual_volume: 9200, time_saved_hours: 0.42, hourly_cost: 58, error_reduction_rate: 14, average_error_cost: 160, revenue_capacity_value: 41000, estimated_annual_cost: 33000, time_to_impact_months: 5, primary_kpi: "Délai de pré-contrôle devis", kpi_target: "-28%", confidence: "high", override: { dimension: "technical_feasibility", score: 3, reason: "Connecteurs chiffrage encore partiels." } }),
  },
  {
    programName: "Programme Fraude",
    useCaseTitle: "Détection signaux fraude corporelle",
    strategicObjective: "Mieux prioriser les dossiers corporels atypiques à forte exposition.",
    scorecard: makeScorecardSeed({ annual_volume: 3600, time_saved_hours: 0.5, hourly_cost: 72, error_reduction_rate: 11, average_error_cost: 420, revenue_capacity_value: 23000, estimated_annual_cost: 31000, time_to_impact_months: 6, primary_kpi: "Taux de dossiers à investiguer priorisés", kpi_target: "+15%", confidence: "low", override: { dimension: "risk_governance", score: 2, reason: "Contrôles renforcés sur les cas sensibles." } }),
  },
  {
    programName: "Programme Réserves",
    useCaseTitle: "Suggestion réserve initiale dommage",
    strategicObjective: "Mieux cadrer les provisions initiales sur les dommages matériels standards.",
    scorecard: makeScorecardSeed({ annual_volume: 12800, time_saved_hours: 0.22, hourly_cost: 49, error_reduction_rate: 19, average_error_cost: 130, revenue_capacity_value: 47000, estimated_annual_cost: 24000, time_to_impact_months: 2, primary_kpi: "Écart entre réserve initiale et clôture", kpi_target: "-18%", confidence: "medium", override: { dimension: "adoption_potential", score: 5, reason: "Managers déjà engagés pour le pilote." } }),
  },
  {
    programName: "Programme Prestataires",
    useCaseTitle: "Routage vers réseau réparateurs agréés",
    strategicObjective: "Orienter plus vite les assurés vers le bon partenaire réparateur.",
    scorecard: makeScorecardSeed({ annual_volume: 21000, time_saved_hours: 0.16, hourly_cost: 39, error_reduction_rate: 17, average_error_cost: 70, revenue_capacity_value: 31000, estimated_annual_cost: 22000, time_to_impact_months: 7, primary_kpi: "Délai d'orientation vers le réparateur", kpi_target: "-25%", confidence: "medium", override: { dimension: "current_friction", score: 4, reason: "Reprises fréquentes sur les zones sous tension." } }),
  },
] as const satisfies ReadonlyArray<SeededCase>;

async function capture(page: Page, order: string, slug: string, assertLoaded: () => Promise<void>) {
  for (const [viewport, size] of CAPTURE_VIEWPORTS) {
    await page.setViewportSize(size);
    await assertLoaded();
    await hideNextDevIndicator(page);
    await page.screenshot({ path: join(CAPTURE_DIR!, `${order}-${slug}-${viewport}.png`), fullPage: true });
  }
}

async function expectNoHorizontalOverflow(page: Page) {
  const metrics = await page.evaluate(() => ({
    bodyWidth: document.body.scrollWidth,
    documentWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));

  expect(metrics.bodyWidth).toBeLessThanOrEqual(metrics.innerWidth + 1);
  expect(metrics.documentWidth).toBeLessThanOrEqual(metrics.innerWidth + 1);
}

async function expectNoQuadrantOverlayCollision(page: Page) {
  const result = await page.evaluate(() => {
    const frame = document.querySelector("[data-portfolio-matrix-frame]");
    if (!(frame instanceof HTMLElement)) {
      return { foundFrame: false, overlaps: ["missing-frame"], outOfBounds: ["missing-frame"] };
    }
    const frameRect = frame.getBoundingClientRect();
    const labels = Array.from(document.querySelectorAll("[data-portfolio-quadrant]"));
    const rects = labels.map((label) => {
      const rect = label.getBoundingClientRect();
      return {
        left: rect.left,
        top: rect.top,
        right: rect.right,
        bottom: rect.bottom,
      };
    });

    const overlaps: string[] = [];
    for (let index = 0; index < rects.length; index += 1) {
      for (let otherIndex = index + 1; otherIndex < rects.length; otherIndex += 1) {
        const current = rects[index];
        const other = rects[otherIndex];
        const intersects =
          current.left < other.right &&
          current.right > other.left &&
          current.top < other.bottom &&
          current.bottom > other.top;
        if (intersects) {
          overlaps.push(`${index}-${otherIndex}`);
        }
      }
    }

    const outOfBounds = rects.flatMap((rect, index) => {
      const failures: string[] = [];
      if (rect.left < frameRect.left || rect.right > frameRect.right) {
        failures.push(`${index}:x`);
      }
      if (rect.top < frameRect.top || rect.bottom > frameRect.bottom) {
        failures.push(`${index}:y`);
      }
      return failures;
    });

    return { foundFrame: true, overlaps, outOfBounds };
  });

  expect(result.foundFrame).toBe(true);
  expect(result.overlaps).toEqual([]);
  expect(result.outOfBounds).toEqual([]);
}

async function expectMobileWizardFormOrdering(page: Page) {
  await page.setViewportSize({ width: 320, height: 844 });

  const activeField = page.getByLabel("Équipe concernée");
  const currentStep = page.locator("[aria-current='step']").first();
  await expect(activeField).toBeVisible();
  await expect(currentStep).toBeVisible();

  const position = async (selector: Locator) =>
    selector.evaluate((node) => node.getBoundingClientRect().top + window.scrollY);

  await expect.poll(async () => {
    const fieldTop = await position(activeField);
    const kickstartTop = await position(page.getByText("Kickstart IA", { exact: true }).first());
    const navigationTop = await position(
      page.getByRole("heading", { name: "Navigation", exact: true }),
    );
    const statusTop = await position(page.getByText("Statut", { exact: true }).first());
    return fieldTop < kickstartTop && fieldTop < navigationTop && fieldTop < statusTop;
  }).toBe(true);
}

test("captures eight seeded studio screens when opted in", async ({ page, request }) => {
  test.skip(!CAPTURE_DIR, "CAPTURE_DIR not set");
  test.setTimeout(900_000);
  await mkdir(CAPTURE_DIR!, { recursive: true });

  const consultant = await fetchDevIdentityHeaders(request, {
    subjectId: "consultant",
    displayName: LOCAL_CONSULTANT_NAME,
    role: "Consultant",
  });
  const seededAt = Date.now();
  const seededCases: Array<{ seed: (typeof SEEDED_CASES)[number]; bootstrap: BootstrapResult }> = [];
  for (const [index, seed] of SEEDED_CASES.entries()) {
    seededCases.push({
      seed,
      bootstrap: await bootstrapUseCase(request, {
        programName: `${seed.programName} ${seededAt}-${index + 1}`,
        useCaseTitle: seed.useCaseTitle,
        strategicObjective: seed.strategicObjective,
      }),
    });
  }
  const [main, ...portfolioCases] = seededCases;
  await fetchDevIdentityHeaders(request, {
    subjectId: "sponsor",
    displayName: LOCAL_SPONSOR_NAME,
    role: "Sponsor",
  });
  const workspaceAdmin = await fetchDevIdentityHeaders(request, {
    subjectId: "workspace-admin",
    displayName: "Administrateur local",
    role: "WorkspaceAdmin",
  });
  const workspacesResponse = await request.get("http://127.0.0.1:8010/api/v1/workspaces", {
    headers: workspaceAdmin.headers,
  });
  expect(workspacesResponse.ok()).toBeTruthy();
  const workspaces = (await workspacesResponse.json()) as {
    items: Array<{ id: string; name: string }>;
  };
  const seededWorkspace = workspaces.items.find((item) => item.id === main.bootstrap.workspaceId);
  expect(seededWorkspace).toBeTruthy();
  const seededWorkspaceName = seededWorkspace?.name ?? "";
  const localizedWorkspaceName = localizeSeededWorkspaceName(seededWorkspaceName);
  await setWorkspaceDefaultLanguage(request, {
    workspaceId: main.bootstrap.workspaceId,
    defaultLanguage: "fr-CA",
  });

  await proxyApiRequests(page, request);
  await selectDevIdentity(page, request, {
    subjectId: "consultant",
    displayName: LOCAL_CONSULTANT_NAME,
    role: "Consultant",
  });

  await page.goto("/studio");
  await capture(page, "01", "dev-identity", async () => {
    await expect(page.getByText(DEV_BANNER)).toBeVisible();
    await expect(page.getByRole("heading", { name: /Piloter les espaces/i })).toBeVisible();
    await expect(page.getByText(LOCAL_CONSULTANT_NAME, { exact: true }).last()).toBeVisible();
    await expect(page.getByText(localizedWorkspaceName, { exact: true })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Parcours studio" })).toHaveCount(0);
    await expect(page.locator("nav[aria-label='Navigation principale']")).toHaveCount(1);
    await expect(page.locator("[aria-current='page']")).toHaveCount(1);
    await expect(page.getByText("Session locale")).toHaveCount(0);
    await expect(page.getByText("Local Consultant", { exact: true })).toHaveCount(0);
    await expect(page.getByText(seededWorkspaceName, { exact: true })).toHaveCount(0);
  });

  await page.goto(`/studio/workspace?workspaceId=${main.bootstrap.workspaceId}`);
  await capture(page, "02", "workspace-home", async () => {
    await expect(page.getByRole("heading", { name: localizedWorkspaceName })).toBeVisible();
    await expect(page.getByText("Langue", { exact: true })).toBeVisible();
    await expect(page.getByText("Programmes de l’espace", { exact: true })).toBeVisible();
    await expect(page.getByText(main.seed.programName, { exact: false }).first()).toBeVisible();
    await expect(page.getByText(main.seed.strategicObjective, { exact: false })).toBeVisible();
    await expect(page.getByText(seededWorkspaceName, { exact: true })).toHaveCount(0);
  });

  await openUseCase(page, main.bootstrap);
  await capture(page, "03", "use-case-detail", async () => {
    await expect(page.getByRole("heading", { name: main.seed.useCaseTitle })).toBeVisible();
    await expect(page.getByText("Opérations")).toBeVisible();
  });

  await page.getByRole("button", { name: /Créer un brouillon d’évaluation|Create draft assessment/ }).click();
  await page.getByLabel("Équipe concernée").fill("Indemnisation auto");
  await page.getByRole("button", { name: /Continuer|Continue/ }).click();
  await expectMobileWizardFormOrdering(page);
  await capture(page, "04", "wizard-validation", async () => {
    await expect(page.getByLabel("Processus cible")).toHaveAttribute("aria-invalid", "true");
    await expect(page.getByRole("alert").first()).toBeVisible();
  });

  await fillStepOne(page);
  await fillStepTwo(page);
  await fillStepThree(page);
  await fillStepFour(page);
  await fillStepFive(page);
  await fillStepSix(page);
  await fillStepSeven(page);
  await capture(page, "05", "wizard-review", async () => {
    await expect(page.getByRole("heading", { name: REVIEW_HEADING })).toBeVisible();
    await expect(page.getByText("Local Sponsor")).toBeVisible();
    await expect(page.getByRole("heading", { name: /Informations manquantes|Missing information/ }).first()).toBeVisible();
  });

  await page.getByLabel("Recommandation préliminaire — Pilot — valider en conditions réelles").check();
  await page.getByLabel("Notes de revue").fill("Pilote sinistres auto centré sur le tri documentaire initial.");
  const submittedAssessment = page.waitForResponse((response) =>
    /\/assessments\/[^/]+\/submit$/.test(new URL(response.url()).pathname) &&
    response.request().method() === "POST",
  );
  await page.getByRole("button", { name: /Soumettre pour revue|Submit for review/ }).click();
  expect((await submittedAssessment).ok()).toBe(true);
  const mainScorecard = (await saveValueAssessmentAndRecalculateScorecard(
    request,
    main.bootstrap,
    consultant.headers,
    main.seed.scorecard,
  )) as ScorecardSnapshot;
  await page.reload();
  await capture(page, "06", "scorecard", async () => {
    await expect(page.getByText(SCORECARD_TITLE)).toBeVisible();
    const bvaDisclosure = page.locator("details").filter({
      has: page.getByText(INSPECT_BVA_DATA),
    }).first();
    await expect(bvaDisclosure).toBeVisible();
    if (!(await bvaDisclosure.evaluate((node) => node.hasAttribute("open")))) {
      await bvaDisclosure.locator("summary").click();
    }
    const netAnnualValue = bvaDisclosure
      .locator("dt", { hasText: /Valeur nette annuelle|Net annual value/ })
      .locator("xpath=following-sibling::dd[1]");
    await expect(netAnnualValue).toContainText(numberPattern(mainScorecard.value_assessment.net_annual_value));
    await expect(page.getByText(mainScorecard.current_scorecard?.category ?? "").first()).toBeVisible();
    await expect(page.getByRole("img", { name: /Jauge du priority score/i })).toBeVisible();
    await expect(page.getByRole("img", { name: /Radar des six dimensions/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Formule/ }).last()).toBeVisible();
  });

  for (const { bootstrap, seed } of portfolioCases) {
    await openUseCase(page, bootstrap);
    await completeAndSubmitWizard(page);
    await saveValueAssessmentAndRecalculateScorecard(request, bootstrap, consultant.headers, seed.scorecard);
  }

  await page.goto(`/studio/portfolio?workspaceId=${main.bootstrap.workspaceId}`);
  await capture(page, "07", "portfolio-matrix", async () => {
    await expect(page.getByRole("heading", { name: PORTFOLIO_TITLE })).toBeVisible();
    const matrixTab = page.getByRole("tab", { name: /Vue matrice|Matrix view/ });
    const listTab = page.getByRole("tab", { name: /Vue liste|List view/ });
    await expect(page.getByRole("tablist")).toBeVisible();
    await expect(matrixTab).toHaveAttribute("aria-selected", "true");
    await expect(listTab).toHaveAttribute("aria-selected", "false");
    await expect(page.locator("g[role='button']")).toHaveCount(6);
    await expect(page.getByRole("button", { name: /FNOL auto prioritaire/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Suggestion réserve initiale dommage/ })).toBeVisible();
    const svgHeight = await page.locator("[data-portfolio-matrix-frame] svg").evaluate((node) => Number(node.getAttribute("height")));
    expect(svgHeight).toBeGreaterThanOrEqual(300);
    await expectNoHorizontalOverflow(page);
    await expectNoQuadrantOverlayCollision(page);

    await matrixTab.focus();
    await matrixTab.press("ArrowRight");
    await expect(listTab).toHaveAttribute("aria-selected", "true");
    await expect(matrixTab).toHaveAttribute("aria-selected", "false");
    await expect(page.getByRole("button", { name: "Suggestion réserve initiale dommage", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Suggestion réserve initiale dommage", exact: true }).click();
    await expect(page.locator("[data-portfolio-summary]")).toContainText("Suggestion réserve initiale dommage");
    await expectNoHorizontalOverflow(page);

    await listTab.focus();
    await listTab.press("ArrowLeft");
    await expect(matrixTab).toHaveAttribute("aria-selected", "true");
    await expect(page.locator("[data-portfolio-summary]")).toContainText("Suggestion réserve initiale dommage");
    await expect(page.locator("g[role='button'][aria-pressed='true']")).toHaveCount(1);
    await expectNoQuadrantOverlayCollision(page);
  });

  await submitReviewAndGenerateBrief(request, main.bootstrap, consultant.headers, {
    recommendation: "Pilot",
    summary: "Le dossier sinistre auto est suffisamment cadré pour un pilote avec validation humaine obligatoire.",
    risks: ["Complétude initiale des pièces", "Calibrage des règles métier sur les cas atypiques"],
  });
  await openUseCase(page, main.bootstrap);
  await capture(page, "08", "document-centre", async () => {
    await expect(page.getByRole("heading", { name: DOCUMENT_CENTRE_TITLE })).toBeVisible();
    await expect(page.getByRole("heading", { name: EXECUTIVE_BRIEF })).toBeVisible();
    await expect(page.getByText(/Version courante/).first()).toBeVisible();
  });
});
