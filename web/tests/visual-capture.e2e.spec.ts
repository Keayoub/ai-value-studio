import { mkdir } from "node:fs/promises";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

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
const DEV_BANNER = /LOCAL DEVELOPMENT — AUTH DISABLED/;
const EXECUTIVE_BRIEF = /Note exécutive/;
const CAPTURE_VIEWPORTS = [
  ["desktop", { width: 1440, height: 900 }],
  ["mobile", { width: 390, height: 844 }],
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
    await page.screenshot({ path: join(CAPTURE_DIR!, `${order}-${slug}-${viewport}.png`), fullPage: true });
  }
}

test("captures eight seeded studio screens when opted in", async ({ page, request }) => {
  test.skip(!CAPTURE_DIR, "CAPTURE_DIR not set");
  test.setTimeout(900_000);
  await mkdir(CAPTURE_DIR!, { recursive: true });

  const consultant = await fetchDevIdentityHeaders(request, {
    subjectId: "consultant",
    displayName: "Local Consultant",
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
  await setWorkspaceDefaultLanguage(request, {
    workspaceId: main.bootstrap.workspaceId,
    defaultLanguage: "fr-CA",
  });

  await proxyApiRequests(page, request);
  await selectDevIdentity(page, request, {
    subjectId: "consultant",
    displayName: "Local Consultant",
    role: "Consultant",
  });

  await page.goto("/studio");
  await capture(page, "01", "dev-identity", async () => {
    await expect(page.getByText(DEV_BANNER)).toBeVisible();
    await expect(page.getByRole("heading", { name: /Piloter les espaces/i })).toBeVisible();
    await expect(page.getByText("Local Consultant", { exact: true }).last()).toBeVisible();
  });

  await page.goto(`/studio/workspace?workspaceId=${main.bootstrap.workspaceId}`);
  await capture(page, "02", "workspace-home", async () => {
    await expect(page.getByRole("heading", { name: "Local Development Workspace" })).toBeVisible();
    await expect(page.getByText("Langue", { exact: true })).toBeVisible();
    await expect(page.getByText("Programmes de l’espace", { exact: true })).toBeVisible();
    await expect(page.getByText(main.seed.programName, { exact: false }).first()).toBeVisible();
    await expect(page.getByText(main.seed.strategicObjective, { exact: false })).toBeVisible();
  });

  await openUseCase(page, main.bootstrap);
  await capture(page, "03", "use-case-detail", async () => {
    await expect(page.getByRole("heading", { name: main.seed.useCaseTitle })).toBeVisible();
    await expect(page.getByText("Opérations")).toBeVisible();
  });

  await page.getByRole("button", { name: /Créer un brouillon d’évaluation|Create draft assessment/ }).click();
  await page.getByLabel("Équipe concernée").fill("Indemnisation auto");
  await page.getByRole("button", { name: /Continuer|Continue/ }).click();
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
  await page.getByRole("button", { name: /Soumettre pour revue|Submit for review/ }).click();
  const mainScorecard = (await saveValueAssessmentAndRecalculateScorecard(
    request,
    main.bootstrap,
    consultant.headers,
    main.seed.scorecard,
  )) as ScorecardSnapshot;
  await page.reload();
  await capture(page, "06", "scorecard", async () => {
    await expect(page.getByText(SCORECARD_TITLE)).toBeVisible();
    await expect(page.getByText(numberPattern(mainScorecard.value_assessment.net_annual_value)).first()).toBeVisible();
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
    await expect(page.locator("g[role='button']")).toHaveCount(6);
    await expect(page.getByRole("button", { name: /FNOL auto prioritaire/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Suggestion réserve initiale dommage/ })).toBeVisible();
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
    await expect(page.getByText(/Version courante/)).toBeVisible();
  });
});
