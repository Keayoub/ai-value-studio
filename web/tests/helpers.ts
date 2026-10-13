import { expect, type APIRequestContext, type Page } from "@playwright/test";

export type DevRole = "Consultant" | "WorkspaceAdmin" | "Sponsor" | "Contributor";

type DevIdentityPayload = {
  display_name: string;
  headers: Record<string, string>;
  oid: string;
};

export type BootstrapResult = {
  workspaceId: string;
  programId: string;
  useCaseId: string;
  sponsorMembershipId: string;
  contributorMembershipId: string;
};

export type ValueAssessmentSeed = {
  annual_volume: number;
  time_saved_hours: number;
  hourly_cost: number;
  error_reduction_rate: number;
  average_error_cost: number;
  revenue_capacity_value: number;
  estimated_annual_cost: number;
  time_to_impact_months: number;
  primary_kpi: string;
  kpi_target: string;
  confidence: "low" | "medium" | "high";
  currency?: string;
  override?: { dimension: string; score: number; reason: string };
};

export type ScorecardSnapshot = {
  current_scorecard: {
    version: number;
    priority_score: number;
    category: string;
  } | null;
  value_assessment: {
    net_annual_value: number;
  };
};

const CREATE_DRAFT_LABEL =
  /Créer un brouillon d’évaluation|Create draft assessment/;
const CONTINUE_LABEL = /Continuer|Continue/;
const SUBMIT_LABEL = /Soumettre pour revue|Submit for review/;

function caseApiPath(bootstrap: BootstrapResult) {
  return `/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}`;
}

async function expectApiOk(
  response: Awaited<ReturnType<APIRequestContext["fetch"]>>,
  context: string,
) {
  const body = await response.text();
  expect(response.ok(), `${context} failed (${response.status()}): ${body}`).toBeTruthy();
}

export async function proxyApiRequests(page: Page, request: APIRequestContext) {
  let apiOnline = true;
  await page.route("**/api/v1/**", async (route) => {
    const browserRequest = route.request();
    const url = new URL(browserRequest.url());
    const isWizardAssessmentRequest = url.pathname.includes("/assessments");
    if (!apiOnline && isWizardAssessmentRequest) {
      await route.abort("internetdisconnected");
      return;
    }
    const response = await request.fetch(
      `http://127.0.0.1:8010${url.pathname}${url.search}`,
      {
        method: browserRequest.method(),
        headers: browserRequest.headers(),
        data: browserRequest.postDataBuffer() ?? undefined,
      },
    );
    await route.fulfill({ response });
  });
  return {
    goOffline() {
      apiOnline = false;
    },
    goOnline() {
      apiOnline = true;
    },
  };
}

export async function fetchDevIdentityHeaders(
  request: APIRequestContext,
  payload: { subjectId: string; displayName: string; role: DevRole },
) {
  const response = await request.post(
    "http://127.0.0.1:8010/api/v1/dev/identity",
    {
      data: {
        subject_id: payload.subjectId,
        display_name: payload.displayName,
        role: payload.role,
      },
    },
  );
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as DevIdentityPayload;
}

export async function selectDevIdentity(
  page: Page,
  request: APIRequestContext,
  payload: { subjectId: string; displayName: string; role: DevRole },
) {
  const selected = await fetchDevIdentityHeaders(request, payload);
  await page.goto("/studio");
  await page.evaluate(
    (identity) => {
      window.localStorage.setItem("avs.dev.identity", JSON.stringify(identity));
    },
    {
      subjectId: selected.oid,
      displayName: selected.display_name,
      role: payload.role,
      headers: selected.headers,
    },
  );
  await page.reload();
}

export async function bootstrapUseCase(
  request: APIRequestContext,
  {
    programName,
    useCaseTitle,
    strategicObjective = "Tester le wizard S4",
  }: {
    programName: string;
    useCaseTitle: string;
    strategicObjective?: string;
  },
) {
  const workspaceAdmin = await fetchDevIdentityHeaders(request, {
    subjectId: "workspace-admin",
    displayName: "Local Workspace Admin",
    role: "WorkspaceAdmin",
  });
  const workspacesResponse = await request.get(
    "http://127.0.0.1:8010/api/v1/workspaces",
    {
      headers: workspaceAdmin.headers,
    },
  );
  expect(workspacesResponse.ok()).toBeTruthy();
  const workspaces = (await workspacesResponse.json()) as {
    items: Array<{ id: string; name: string }>;
  };
  const workspaceId = workspaces.items[0]?.id;
  expect(workspaceId).toBeTruthy();

  const membersResponse = await request.get(
    `http://127.0.0.1:8010/api/v1/workspaces/${workspaceId}/members`,
    {
      headers: workspaceAdmin.headers,
    },
  );
  expect(membersResponse.ok()).toBeTruthy();
  const members = (await membersResponse.json()) as {
    items: Array<{
      membership_id: string;
      identity: { display_name: string | null };
    }>;
  };
  const sponsorMembershipId =
    members.items.find(
      (member) => member.identity.display_name === "Local Sponsor",
    )?.membership_id ?? "";
  const contributorMembershipId =
    members.items.find(
      (member) => member.identity.display_name === "Local Contributor",
    )?.membership_id ?? "";
  expect(sponsorMembershipId).toBeTruthy();
  expect(contributorMembershipId).toBeTruthy();

  const programResponse = await request.post(
    `http://127.0.0.1:8010/api/v1/workspaces/${workspaceId}/programs`,
    {
      headers: {
        ...workspaceAdmin.headers,
        "Content-Type": "application/json",
      },
      data: {
        name: programName,
        strategic_objective: strategicObjective,
        sponsor_membership_id: sponsorMembershipId,
      },
    },
  );
  expect(programResponse.ok()).toBeTruthy();
  const program = (await programResponse.json()) as { id: string };

  const assignResponse = await request.post(
    `http://127.0.0.1:8010/api/v1/workspaces/${workspaceId}/programs/${program.id}/members`,
    {
      headers: {
        ...workspaceAdmin.headers,
        "Content-Type": "application/json",
      },
      data: {
        membership_id: contributorMembershipId,
        assignment_role: "Contributor",
      },
    },
  );
  expect(assignResponse.ok()).toBeTruthy();

  const useCaseResponse = await request.post(
    `http://127.0.0.1:8010/api/v1/workspaces/${workspaceId}/programs/${program.id}/use-cases`,
    {
      headers: {
        ...workspaceAdmin.headers,
        "Content-Type": "application/json",
      },
      data: {
        title: useCaseTitle,
        department: "Opérations",
        owner_membership_id: contributorMembershipId,
      },
    },
  );
  expect(useCaseResponse.ok()).toBeTruthy();
  const useCase = (await useCaseResponse.json()) as { id: string };

  return {
    workspaceId,
    programId: program.id,
    useCaseId: useCase.id,
    sponsorMembershipId,
    contributorMembershipId,
  } satisfies BootstrapResult;
}

export async function setWorkspaceDefaultLanguage(
  request: APIRequestContext,
  {
    workspaceId,
    defaultLanguage,
  }: {
    workspaceId: string;
    defaultLanguage: string;
  },
) {
  const workspaceAdmin = await fetchDevIdentityHeaders(request, {
    subjectId: "workspace-admin",
    displayName: "Local Workspace Admin",
    role: "WorkspaceAdmin",
  });
  const response = await request.patch(
    `http://127.0.0.1:8010/api/v1/workspaces/${workspaceId}`,
    {
      headers: {
        ...workspaceAdmin.headers,
        "Content-Type": "application/json",
      },
      data: {
        default_language: defaultLanguage,
      },
    },
  );
  await expectApiOk(response, "Updating workspace default language");
  const workspace = (await response.json()) as { default_language: string };
  expect(workspace.default_language).toBe(defaultLanguage);
  return workspace;
}

export async function openUseCase(page: Page, bootstrap: BootstrapResult) {
  await page.goto(
    `/studio/use-case?workspaceId=${bootstrap.workspaceId}&programId=${bootstrap.programId}&useCaseId=${bootstrap.useCaseId}`,
  );
}

export async function saveValueAssessmentAndRecalculateScorecard(
  request: APIRequestContext,
  bootstrap: BootstrapResult,
  headers: Record<string, string>,
  { override, currency = "EUR", ...data }: ValueAssessmentSeed,
) {
  await expectApiOk(
    await request.put(`http://127.0.0.1:8010${caseApiPath(bootstrap)}/value-assessment`, {
      headers,
      data: { ...data, currency },
    }),
    "Saving value assessment",
  );
  await expectApiOk(
    await request.post(`http://127.0.0.1:8010${caseApiPath(bootstrap)}/scorecards/recalculate`, {
      headers,
    }),
    "Recalculating scorecard",
  );
  if (override) {
    await expectApiOk(
      await request.post(`http://127.0.0.1:8010${caseApiPath(bootstrap)}/scorecards/override`, {
        headers,
        data: override,
      }),
      "Overriding scorecard",
    );
  }
  return fetchScorecardSnapshot(request, bootstrap, headers);
}

export async function fetchScorecardSnapshot(
  request: APIRequestContext,
  bootstrap: BootstrapResult,
  headers: Record<string, string>,
) {
  const response = await request.get(`http://127.0.0.1:8010${caseApiPath(bootstrap)}/scorecards`, {
    headers,
  });
  await expectApiOk(response, "Fetching scorecard");
  return (await response.json()) as ScorecardSnapshot;
}

export async function submitReviewAndGenerateBrief(
  request: APIRequestContext,
  bootstrap: BootstrapResult,
  headers: Record<string, string>,
  {
    recommendation,
    summary,
    risks,
    language = "fr",
  }: {
    recommendation: string;
    summary: string;
    risks: string[];
    language?: string;
  },
) {
  await expectApiOk(
    await request.post(`http://127.0.0.1:8010${caseApiPath(bootstrap)}/reviews`, {
      headers,
      data: { recommendation, summary, risks },
    }),
    "Submitting review",
  );
  await expectApiOk(
    await request.post(`http://127.0.0.1:8010${caseApiPath(bootstrap)}/documents`, {
      headers: {
        ...headers,
        "Idempotency-Key": `visual-capture-${bootstrap.useCaseId}`,
      },
      data: { type: "ExecutiveBrief", format: "markdown", language },
    }),
    "Generating executive brief",
  );
}

export async function fillStepOne(page: Page) {
  await page
    .getByLabel("Processus cible")
    .fill("Qualifier les dossiers entrants avant affectation.");
  await page.getByLabel("Équipe concernée").fill("Équipe opérations");
  await page
    .getByLabel("Déclencheur principal")
    .fill("Réception d'un nouveau dossier");
  await page
    .getByLabel("Étapes principales du processus")
    .fill("Réception\nContrôle des pièces\nQualification\nAffectation");
  await page.getByLabel("Systèmes impliqués").fill("GED, CRM, portail client");
  await page.getByLabel("Volume annualisé").fill("12000");
  await page.getByLabel("Durée moyenne par occurrence (minutes)").fill("25");
  await page.getByRole("button", { name: CONTINUE_LABEL }).click();
}

export async function fillStepTwo(page: Page) {
  await page
    .getByLabel("Problème observé")
    .fill("Le tri initial des dossiers est trop lent et manque de cohérence.");
  await page
    .getByLabel("Causes de délai, coût ou risque")
    .fill("Règles dispersées, relectures multiples et pièces manquantes.");
  await page
    .getByLabel("Points d'erreur ou de rupture")
    .fill("Affectation initiale incorrecte et oublis sur les pièces.");
  await page
    .getByLabel("Connaissances manquantes")
    .fill("Exceptions rares et règles tacites.");
  await page.getByLabel("Impact principal").selectOption("quantified");
  await page
    .getByLabel("Impact documenté")
    .fill("Le délai moyen augmente de deux jours.");
  await page
    .getByLabel("Coût de l'inaction")
    .fill("Retards, surcharge et insatisfaction.");
  await page
    .getByLabel("Pourquoi maintenant")
    .fill("Le volume augmente et les SLA se dégradent.");
  await page
    .getByLabel("Éléments de preuve")
    .fill("Mesures internes et retours des gestionnaires.");
  await page.getByRole("button", { name: CONTINUE_LABEL }).click();
}

export async function fillStepThree(
  page: Page,
  options: { continueAfter?: boolean } = {},
) {
  await page
    .getByLabel("Tâche réalisée par l'IA")
    .fill("Analyser le dossier et recommander la prochaine action.");
  await page
    .getByLabel("Entrées attendues")
    .fill("Dossier PDF, métadonnées et pièces jointes.");
  await page
    .getByLabel("Sorties attendues")
    .fill("Résumé, anomalies et action recommandée.");
  await page.getByLabel("Niveau d'autonomie — Recommander").check();
  await page.getByLabel("Validation humaine — Obligatoire").check();
  await page.getByLabel("Langues à supporter").fill("Français\nanglais");
  await page
    .getByLabel("Comportements interdits")
    .fill("Aucune décision finale sans validation humaine.");
  await page
    .getByLabel("Pattern de solution")
    .selectOption("ai_case_processing");
  await page.getByLabel("Type de dossier").fill("Sinistre automobile");
  await page.getByLabel("Volume de dossiers concerné").fill("12000");
  await page.getByLabel("Documents par dossier").fill("8");
  await page
    .getByLabel("Documents obligatoires")
    .fill("Déclaration, photos, devis.");
  await page
    .getByLabel("Champs à extraire")
    .fill("Plaque, date, assurés, montant.");
  await page
    .getByLabel("Contrôles d'incohérence")
    .fill("Dates, pièces manquantes, doublons.");
  await page
    .getByLabel("Action suivante attendue")
    .fill("Affectation au gestionnaire.");
  await page.getByLabel("SLA ou délai cible").fill("30 minutes");
  await page
    .getByLabel("Niveau de validation humaine")
    .selectOption("mandatory");
  await page
    .getByLabel("Coût d'un traitement incomplet ou erroné")
    .fill("Retards d'indemnisation et réclamations client.");
  await page
    .getByLabel(
      "Données personnelles, médicales ou financières concernées — Personnelles",
    )
    .check();
  await page
    .getByLabel(
      "Données personnelles, médicales ou financières concernées — Financières",
    )
    .check();
  if (options.continueAfter ?? true) {
    await page.getByRole("button", { name: CONTINUE_LABEL }).click();
  }
}

export async function fillStepFour(page: Page) {
  await page.getByLabel("Temps gagné par transaction (heures)").fill("0.2");
  await page.getByLabel("Coût horaire moyen").fill("45");
  await page.getByLabel("Réduction attendue du taux d'erreur (%)").fill("20");
  await page.getByLabel("Coût moyen d'une erreur").fill("85");
  await page.getByLabel("Impact annuel revenu/capacité").fill("15000");
  await page.getByLabel("Coût annuel estimé de la solution").fill("25000");
  await page.getByLabel("Temps avant impact (mois)").fill("4");
  await page.getByLabel("KPI principal").fill("Temps moyen de qualification");
  await page.getByLabel("Cible du KPI").fill("-30%");
  await page
    .getByLabel("Confiance sur l'hypothèse de valeur")
    .selectOption("medium");
  await page
    .getByLabel("Hypothèse principale de valeur")
    .fill("L'automatisation assistée réduit les relectures manuelles.");
  await expect(page.getByText(/302.?000/)).toBeVisible();
  await page.getByRole("button", { name: CONTINUE_LABEL }).click();
}

export async function fillStepFive(page: Page) {
  await page
    .getByLabel("Sources de données")
    .fill("GED\nCRM\nExports d'activité");
  await page
    .getByLabel("Propriétaire des données")
    .fill("Responsable opérations");
  await page.getByLabel("Disponibilité").selectOption("available");
  await page.getByLabel("Type de données").selectOption("document");
  await page.getByLabel("Qualité des données (1-5) — 3").check();
  await page.getByLabel("Accessibilité pour un pilote").selectOption("ready");
  await page
    .getByLabel("Présence de données personnelles ou sensibles")
    .selectOption("personal");
  await page
    .getByLabel("Connecteurs ou extractions nécessaires")
    .fill("Connecteur GED.");
  await page.getByRole("button", { name: CONTINUE_LABEL }).click();
}

export async function fillStepSix(page: Page) {
  await page
    .getByLabel("Systèmes et dépendances")
    .fill("GED, CRM et annuaire.");
  await page.getByLabel("Environnement accepté").selectOption("customer_vpc");
  await page
    .getByLabel("Exigence de latence / disponibilité")
    .fill("30 secondes max.");
  await page
    .getByLabel("Compétences de l'équipe")
    .fill("BA, ops et support applicatif.");
  await page.getByLabel("Responsable support / run").fill("Lead opérations");
  await page.getByLabel("Besoins de formation").fill("Demi-journée.");
  await page
    .getByLabel("Dépendance clé ou mention 'aucune'")
    .fill("Validation sécurité et accès GED.");
  await page
    .getByLabel("Bande d'effort / investissement")
    .selectOption("medium");
  await page.getByRole("button", { name: CONTINUE_LABEL }).click();
}

export async function fillStepSeven(page: Page) {
  await page.getByLabel("Impact d'une mauvaise réponse").selectOption("high");
  await page
    .getByLabel(
      /La décision impacte-t-elle une personne \? — Oui|La décision impacte-t-elle une personne \? — Yes/,
    )
    .check();
  await page
    .getByLabel(
      /Une explicabilité est-elle requise \? — Oui|Une explicabilité est-elle requise \? — Yes/,
    )
    .check();
  await page.getByLabel("Validation humaine requise").selectOption("mandatory");
  await page.getByLabel("Frontière de données").selectOption("internal_only");
  await page
    .getByLabel(
      /Traçabilité \/ audit requis — Oui|Traçabilité \/ audit requis — Yes/,
    )
    .check();
  await page.getByLabel("Modèle d'accès").selectOption("rbac");
  await page
    .getByLabel("Contraintes conformité")
    .fill("Journalisation et conservation 12 mois.");
  await page.getByLabel("Responsable du risque").fill("Sponsor métier");
  await page
    .getByLabel("Plan de mitigation")
    .fill("Validation humaine obligatoire et seuils de contrôle.");
  await page
    .getByLabel(
      /Risque accepté pour une recommandation Go\/Pilot — Oui|Risque accepté pour une recommandation Go\/Pilot — Yes/,
    )
    .check();
  await page
    .getByLabel("Hypothèse de risque à valider")
    .fill("Le taux de faux positifs doit rester sous 5%.");
  await page.getByRole("button", { name: CONTINUE_LABEL }).click();
}

export async function completeAndSubmitWizard(page: Page) {
  await page.getByRole("button", { name: CREATE_DRAFT_LABEL }).click();
  await fillStepOne(page);
  await fillStepTwo(page);
  await fillStepThree(page);
  await fillStepFour(page);
  await fillStepFive(page);
  await fillStepSix(page);
  await fillStepSeven(page);
  await page
    .getByLabel(
      "Recommandation préliminaire — Pilot — valider en conditions réelles",
    )
    .check();
  await page
    .getByLabel("Notes de revue")
    .fill("Pilote limité au tri initial avec revue humaine obligatoire.");
  const submitted = page.waitForResponse((response) =>
    /\/assessments\/[^/]+\/submit$/.test(new URL(response.url()).pathname) &&
    response.request().method() === "POST",
  );
  await page.getByRole("button", { name: SUBMIT_LABEL }).click();
  expect((await submitted).ok(), "Submitting assessment").toBe(true);
}
