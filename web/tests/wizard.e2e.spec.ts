import { readFile } from "node:fs/promises";

import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type APIRequestContext,
  type Locator,
  type Page,
} from "@playwright/test";
import type { KickstartSuggestion } from "@/features/api/types";

type DevRole = "Consultant" | "WorkspaceAdmin" | "Sponsor" | "Contributor";

type DevIdentityPayload = {
  display_name: string;
  headers: Record<string, string>;
  oid: string;
};

type BootstrapResult = {
  workspaceId: string;
  programId: string;
  useCaseId: string;
  sponsorMembershipId: string;
  contributorMembershipId: string;
};

type AssertableResponse = {
  ok(): boolean;
  status(): number;
  statusText(): string;
  text(): Promise<string>;
};

type ReviewStateResponse = {
  review: {
    id: string;
    status: "Submitted" | "ChangesRequested" | "Approved" | "Rejected";
    summary: string;
    risks: string[];
    submitted_at: string;
  } | null;
};

const CREATE_DRAFT_LABEL =
  /Créer un brouillon d’évaluation|Create draft assessment/;
const CONTINUE_LABEL = /Continuer|Continue/;
const KICKSTART_TITLE = /Kickstart IA|AI kickstart/;
const KICKSTART_DISABLED_TEXT =
  /L’assistance IA est désactivée pour cet espace|AI assistance is disabled for this workspace/;
const GENERATE_KICKSTART_LABEL =
  /Générer une proposition IA|Generate AI proposal/;
const KICKSTART_APPLIED_TEXT =
  /Suggestion enregistrée comme réponse assistée par IA|Suggestion saved as an AI-assisted answer/;
const KICKSTART_CONFIRM_TITLE =
  /Confirmer le remplacement de la réponse actuelle|Confirm replacing the current answer/;
const KICKSTART_CONFIRM_BUTTON =
  /Confirmer le remplacement|Confirm replacement/;
const KICKSTART_IGNORED_TEXT =
  /Proposition ignorée pour ce champ\.|Proposal ignored for this field\./;
const KICKSTART_PROBLEM_HEADING = /Problème|Problem statement/;
const KICKSTART_KPI_HEADING = /Propositions de KPI|KPI proposals/;
const KICKSTART_RISKS_HEADING = /Risques|Risks/;
const KICKSTART_PROBLEM_PROPOSAL_LABEL =
  /Problème — Proposition IA éditable|Problem statement — Editable AI proposal/;
const KICKSTART_KPI_PROPOSAL_LABEL =
  /Propositions de KPI — Proposition IA éditable|KPI proposals — Editable AI proposal/;
const INTERVIEW_MODE_LABEL = /Mode entretien|Interview mode/;
const RESPONDENT_LABEL = /Répondant|Respondent/;
const INTERVIEW_ACTIVE_TEXT = /Mode entretien actif|Interview mode active/;
const SAVED_AT_TEXT = /Enregistré à|Saved at/;
const REVIEW_HEADING = /Revue avant soumission|Review before submission/;
const SUBMIT_LABEL = /Soumettre pour revue|Submit for review/;
const NEW_DRAFT_LABEL =
  /Créer une nouvelle version brouillon|Create new draft version/;
const READ_ONLY_TEXT = /Lecture seule|Read only/;
const REVIEW_PANEL_TITLE = /Revue sponsor|Sponsor review/;
const NO_REVIEW_TITLE = /Aucune revue soumise|No submitted review/;
const REVIEW_SUBMIT_BUTTON = /Soumettre la revue|Submit review/;
const REVIEW_SUMMARY_LABEL = /Synthèse|Summary/;
const REVIEW_RISKS_LABEL =
  /Risques et points d’attention|Risks and watchpoints/;
const REVIEW_INBOX_TITLE = /À traiter|Action queue/;
const OPEN_REVIEW_LINK = /Ouvrir la revue|Open review/;
const ADD_COMMENT_LABEL = /Ajouter un commentaire|Add comment/;
const DECISION_REASON_LABEL = /Motif .*décision|Decision reason/;
const APPROVE_REVIEW_LABEL =
  /Approuver la recommandation|Approve recommendation/;
const REQUEST_CHANGES_LABEL = /Demander des changements|Request changes/;
const CONFIRM_DECISION_LABEL =
  /Je confirme cette décision|I confirm this decision/;
const PREVIOUS_CYCLES_TITLE = /Cycles précédents|Previous cycles/;
const MISSING_INFORMATION_TEXT = /Informations manquantes|Missing information/;
const SCORECARD_TITLE =
  /Scorecard de valeur et de priorité|Value and priority scorecard/;
const RECALCULATE_SCORECARD = /Recalculer le scorecard|Recalculate scorecard/;
const OVERRIDE_SCORECARD = /Surcharge consultant|Consultant override/;
const SUBMIT_OVERRIDE = /Créer la nouvelle version|Create new version/;
const SCORECARD_RECALCULATED_TOAST =
  /Scorecard recalculé|Scorecard recalculated/;
const DOCUMENT_CENTRE_TITLE = /Centre documentaire|Document centre/;
const PORTFOLIO_TITLE = /Matrice portefeuille IA|AI portfolio matrix/;
const PORTFOLIO_TABLE_VIEW = /Vue tableau|Table view/;
const PORTFOLIO_MATRIX_VIEW = /Vue matrice|Matrix view/;
const PORTFOLIO_PROGRAM_FILTER = /Programme|Program/;
const REVENUE_CAPACITY_LABEL =
  /Impact annuel revenu\/capacité|Annual revenue\/capacity impact/;
const OVERRIDE_REASON_LABEL = /Raison de la surcharge|Override reason/;
const REQUEST_INFORMATION_LIMITATION_TEXT =
  /Cette action reste indisponible tant qu’aucune API autorisée ne peut enregistrer une demande d’informations\.|This action stays unavailable until an authorized API can persist an information request\./;
const AI_ASSISTED_TEXT = /^(Assisté par IA|AI-assisted)$/;

function formatApiFailureBody(bodyText: string) {
  if (!bodyText) {
    return "<empty response body>";
  }

  try {
    return JSON.stringify(JSON.parse(bodyText), null, 2);
  } catch {
    return bodyText;
  }
}

function truncateForAssertion(value: string, maxLength = 4_000) {
  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, maxLength)}\n…<truncated ${value.length - maxLength} characters>`;
}

async function expectApiOk(response: AssertableResponse, context: string) {
  const bodyText = await response.text();
  expect(
    response.ok(),
    `${context} failed with ${response.status()} ${response.statusText()}\nResponse body:\n${truncateForAssertion(formatApiFailureBody(bodyText))}`,
  ).toBeTruthy();
  return bodyText;
}

async function expectApiJson<T>(response: AssertableResponse, context: string) {
  const bodyText = await expectApiOk(response, context);
  return JSON.parse(bodyText) as T;
}

async function proxyApiRequests(page: Page, request: APIRequestContext) {
  let apiOnline = true;
  await page.route("**/api/v1/**", async (route) => {
    const browserRequest = route.request();
    const url = new URL(browserRequest.url());
    const isWizardAssessmentRequest = url.pathname.includes("/assessments");
    if (!apiOnline) {
      if (isWizardAssessmentRequest) {
        await route.abort("internetdisconnected");
        return;
      }
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

async function setWorkspaceAiAssistance(
  request: APIRequestContext,
  {
    workspaceId,
    headers,
    enabled,
    note,
  }: {
    workspaceId: string;
    headers: Record<string, string>;
    enabled: boolean;
    note: string;
  },
) {
  const response = await request.patch(
    `http://127.0.0.1:8010/api/v1/workspaces/${workspaceId}`,
    {
      headers: {
        ...headers,
        "Content-Type": "application/json",
      },
      data: {
        ai_assistance_enabled: enabled,
        ai_assistance_data_processing_note: note,
      },
    },
  );
  return expectApiJson<{
    ai_assistance_enabled: boolean;
    ai_assistance_available: boolean;
    ai_assistance_consent_at: string | null;
    ai_assistance_data_processing_note: string | null;
  }>(response, "Updating workspace AI assistance");
}

async function selectDevIdentity(
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

async function fetchDevIdentityHeaders(
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

async function bootstrapUseCase(
  request: APIRequestContext,
  {
    programName,
    useCaseTitle,
  }: {
    programName: string;
    useCaseTitle: string;
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
        strategic_objective: "Tester le wizard S4",
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

async function createDraftAssessment(
  request: APIRequestContext,
  bootstrap: BootstrapResult,
  headers: Record<string, string>,
) {
  const response = await request.post(
    `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/assessments`,
    {
      headers: {
        ...headers,
        "Content-Type": "application/json",
      },
      data: {},
    },
  );
  return expectApiJson<{ assessment: { id: string } }>(response, "Creating draft assessment");
}

async function seedAssessmentAnswers(
  request: APIRequestContext,
  {
    bootstrap,
    assessmentId,
    headers,
    answers,
  }: {
    bootstrap: BootstrapResult;
    assessmentId: string;
    headers: Record<string, string>;
    answers: Record<string, string>;
  },
) {
  for (const [questionKey, value] of Object.entries(answers)) {
    const response = await request.put(
      `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/assessments/${assessmentId}/answers/${questionKey}`,
      {
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        data: {
          value,
          source: "human",
        },
      },
    );
    await expectApiOk(response, `Seeding answer ${questionKey}`);
  }
}

async function expectNoTaggedAxeViolations(
  page: Page,
  options: { allowRuleIds?: string[] } = {},
) {
  await waitForStableAxeTarget(page);
  const accessibilityScan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const allowedRuleIds = new Set(options.allowRuleIds ?? []);
  const wcagViolations = accessibilityScan.violations.filter(
    (violation) => !allowedRuleIds.has(violation.id),
  );
  expect(wcagViolations).toEqual([]);
}

async function waitForStableAxeTarget(page: Page) {
  await page.waitForLoadState("domcontentloaded");
  await expect
    .poll(() => page.title(), {
      message: "Expected a non-empty document title before running axe.",
      timeout: 5_000,
    })
    .toMatch(/\S/);
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => resolve());
      });
    });
  });
  await page.waitForFunction(
    () =>
      document
        .getAnimations()
        .filter((animation) => {
          const timing = animation.effect?.getComputedTiming();
          return (
            typeof timing?.duration === "number" &&
            timing.duration > 0 &&
            timing.iterations !== Infinity
          );
        })
        .every(
          (animation) =>
            animation.playState === "finished" ||
            animation.playState === "idle",
        ),
    null,
    { timeout: 5_000 },
  );
}

function numberPattern(value: number) {
  const digits = Math.round(value).toString();
  if (digits.length <= 3) {
    return new RegExp(digits);
  }
  const head = digits.slice(0, -3);
  const tail = digits.slice(-3);
  return new RegExp(`${head}[\\s,.  ]?${tail}`);
}

function kickstartCard(page: Page, headingName: RegExp): Locator {
  return page
    .getByRole("heading", { name: headingName })
    .locator("xpath=ancestor::section[1]");
}

async function openUseCase(page: Page, bootstrap: BootstrapResult) {
  await page.goto(
    `/studio/use-case?workspaceId=${bootstrap.workspaceId}&programId=${bootstrap.programId}&useCaseId=${bootstrap.useCaseId}`,
  );
}

async function submitReviewAndWaitForPersistence(
  page: Page,
  request: APIRequestContext,
  {
    bootstrap,
    headers,
    summary,
    risks,
  }: {
    bootstrap: BootstrapResult;
    headers: Record<string, string>;
    summary: string;
    risks: string[];
  },
) {
  const browserPath = `/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/reviews`;
  const backendUrl = `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/review`;
  const submitResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "POST" && url.pathname === browserPath;
  });

  await page.getByRole("button", { name: REVIEW_SUBMIT_BUTTON }).click();

  const submittedState = await expectApiJson<ReviewStateResponse>(
    await submitResponsePromise,
    "Submitting review",
  );
  expect(submittedState.review).toMatchObject({
    status: "Submitted",
    summary,
    risks,
  });
  expect(submittedState.review?.submitted_at).toBeTruthy();

  const submittedReviewId = submittedState.review?.id ?? "";
  expect(submittedReviewId).toBeTruthy();

  await expect
    .poll(async () => {
      const response = await request.get(backendUrl, {
        headers,
      });
      const body = await expectApiJson<ReviewStateResponse>(
        response,
        "Polling submitted review",
      );
      return body.review
        ? {
            id: body.review.id,
            status: body.review.status,
            summary: body.review.summary,
            risks: body.review.risks,
            hasSubmittedAt: Boolean(body.review.submitted_at),
          }
        : null;
    })
    .toEqual({
      id: submittedReviewId,
      status: "Submitted",
      summary,
      risks,
      hasSubmittedAt: true,
    });
}

async function fillStepOne(page: Page) {
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

async function fillStepTwo(page: Page) {
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

async function fillStepThree(
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

async function fillStepFour(page: Page) {
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

async function fillStepFive(page: Page) {
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

async function fillStepSix(page: Page) {
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

async function fillStepSeven(page: Page) {
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

async function completeAndSubmitWizard(page: Page) {
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
  await page.getByRole("button", { name: SUBMIT_LABEL }).click();
}

async function seedScorecardSnapshot(
  page: Page,
  request: APIRequestContext,
  {
    bootstrap,
    consultantHeaders,
    revenueCapacityValue,
  }: {
    bootstrap: BootstrapResult;
    consultantHeaders: Record<string, string>;
    revenueCapacityValue: number;
  },
) {
  await openUseCase(page, bootstrap);
  await completeAndSubmitWizard(page);
  const assessmentResponse = await request.put(
    `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/value-assessment`,
    {
      headers: consultantHeaders,
      data: {
        annual_volume: 12000,
        time_saved_hours: 0.2,
        hourly_cost: 45,
        error_reduction_rate: 20,
        average_error_cost: 85,
        revenue_capacity_value: revenueCapacityValue,
        estimated_annual_cost: 25000,
        time_to_impact_months: 4,
        primary_kpi: "Temps moyen de qualification",
        kpi_target: "-30%",
        confidence: "medium",
        currency: "EUR",
      },
    },
  );
  await expectApiOk(assessmentResponse, "Saving portfolio value assessment");

  const recalculateResponse = await request.post(
    `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/scorecards/recalculate`,
    {
      headers: consultantHeaders,
    },
  );
  await expectApiOk(recalculateResponse, "Recalculating portfolio scorecard");
}

test("completes the persisted eight-step wizard, reloads cleanly, and submits", async ({
  page,
  request,
}) => {
  const consultant = await fetchDevIdentityHeaders(request, {
    subjectId: "consultant",
    displayName: "Local Consultant",
    role: "Consultant",
  });
  const bootstrap = await bootstrapUseCase(request, {
    programName: `Programme wizard ${Date.now()}`,
    useCaseTitle: `Cas wizard ${Date.now()}`,
  });
  await proxyApiRequests(page, request);
  await selectDevIdentity(page, request, {
    subjectId: "consultant",
    displayName: "Local Consultant",
    role: "Consultant",
  });

  await openUseCase(page, bootstrap);
  await page.getByRole("button", { name: CREATE_DRAFT_LABEL }).click();
  await expect(page.getByText(KICKSTART_TITLE)).toBeVisible();
  await expect(page.getByText(KICKSTART_DISABLED_TEXT)).toBeVisible();
  await expect(
    page.getByRole("button", { name: GENERATE_KICKSTART_LABEL }),
  ).toHaveCount(0);
  await page.setViewportSize({ width: 320, height: 900 });
  await expectNoTaggedAxeViolations(page);
  await page.setViewportSize({ width: 1440, height: 1200 });
  await fillStepOne(page);
  await fillStepTwo(page);

  await page.reload();
  await expect(page.getByLabel("Problème observé")).toHaveValue(
    "Le tri initial des dossiers est trop lent et manque de cohérence.",
  );
  await page.getByRole("button", { name: CONTINUE_LABEL }).click();
  await expect(page.getByLabel("Tâche réalisée par l'IA")).toBeVisible();
  await expectNoTaggedAxeViolations(page);

  await fillStepThree(page, { continueAfter: false });
  await expectNoTaggedAxeViolations(page);
  await page.getByRole("button", { name: CONTINUE_LABEL }).click();
  await fillStepFour(page);
  await fillStepFive(page);
  await fillStepSix(page);
  await fillStepSeven(page);

  await expect(
    page.getByRole("heading", { name: REVIEW_HEADING }),
  ).toBeVisible();
  await expectNoTaggedAxeViolations(page);
  await expect(
    page.getByText(REQUEST_INFORMATION_LIMITATION_TEXT),
  ).toBeVisible();
  await expect(
    page.getByRole("definition").filter({ hasText: "Local Sponsor" }),
  ).toBeVisible();
  await page
    .getByLabel(
      "Recommandation préliminaire — Pilot — valider en conditions réelles",
    )
    .check();
  await page
    .getByLabel("Notes de revue")
    .fill("Pilote limité au tri initial avec revue humaine obligatoire.");
  await page.getByRole("button", { name: SUBMIT_LABEL }).click();

  await expect(
    page.getByRole("heading", { name: REVIEW_PANEL_TITLE }),
  ).toBeVisible();
  await expect(page.getByText(NO_REVIEW_TITLE)).toBeVisible();
  await expect(page.getByText(READ_ONLY_TEXT)).toBeVisible();
  await expect(page.getByText(SCORECARD_TITLE)).toBeVisible();
  await page.getByLabel(REVENUE_CAPACITY_LABEL).fill("18000");
  await page.getByRole("button", { name: RECALCULATE_SCORECARD }).click();
  await expect(page.getByText(SCORECARD_RECALCULATED_TOAST)).toBeVisible();

  await expect
    .poll(async () => {
      const response = await request.get(
        `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/scorecards`,
        {
          headers: consultant.headers,
        },
      );
      const body = await expectApiJson<{
        current_scorecard: { version: number } | null;
      }>(response, "Polling scorecard recalculation");
      return body.current_scorecard?.version ?? 0;
    })
    .toBe(1);
  const recalculatedResponse = await request.get(
    `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/scorecards`,
    {
      headers: consultant.headers,
    },
  );
  const recalculatedBody = await expectApiJson<{
    current_scorecard: {
      version: number;
      priority_score: number;
      category: string;
    } | null;
    value_assessment: { net_annual_value: number };
  }>(recalculatedResponse, "Fetching recalculated scorecard");
  await expect(
    page
      .getByText(
        numberPattern(recalculatedBody.value_assessment.net_annual_value),
      )
      .first(),
  ).toBeVisible();
  await expect(
    page
      .getByText(
        recalculatedBody.current_scorecard?.priority_score.toFixed(3) ?? "",
      )
      .first(),
  ).toBeVisible();
  const overrideButton = page
    .getByRole("button", { name: OVERRIDE_SCORECARD })
    .first();
  await expect(overrideButton).toBeVisible();
  await overrideButton.click();
  await page
    .getByLabel(OVERRIDE_REASON_LABEL)
    .fill("Mitigation formalisée et contrôles RBAC validés.");
  await page.getByRole("button", { name: SUBMIT_OVERRIDE }).click();
  await expect(page.getByText("Version").first()).toBeVisible();
  await expectNoTaggedAxeViolations(page);

  const scorecardResponse = await request.get(
    `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/scorecards`,
    {
      headers: consultant.headers,
    },
  );
  const scorecardBody = await expectApiJson<{
    current_scorecard: {
      version: number;
      priority_score: number;
      category: string;
    };
    value_assessment: { net_annual_value: number };
  }>(scorecardResponse, "Fetching overridden scorecard");
  expect(scorecardBody.current_scorecard.version).toBe(2);
  await expect(
    page
      .getByText(scorecardBody.current_scorecard.priority_score.toFixed(3))
      .first(),
  ).toBeVisible();
  await expect(
    page.getByText(scorecardBody.current_scorecard.category).first(),
  ).toBeVisible();
  await expect(
    page
      .getByText(numberPattern(scorecardBody.value_assessment.net_annual_value))
      .first(),
  ).toBeVisible();
});

test("reviews and applies an AI proposal with explicit overwrite confirmation", async ({
  page,
  request,
}) => {
  const workspaceAdmin = await fetchDevIdentityHeaders(request, {
    subjectId: "workspace-admin",
    displayName: "Local Workspace Admin",
    role: "WorkspaceAdmin",
  });
  const consultant = await fetchDevIdentityHeaders(request, {
    subjectId: "consultant",
    displayName: "Local Consultant",
    role: "Consultant",
  });
  const bootstrap = await bootstrapUseCase(request, {
    programName: `Programme kickstart ${Date.now()}`,
    useCaseTitle: `Cas kickstart ${Date.now()}`,
  });
  await proxyApiRequests(page, request);

  const createdAssessment = await createDraftAssessment(
    request,
    bootstrap,
    consultant.headers,
  );
  await seedAssessmentAnswers(request, {
    bootstrap,
    assessmentId: createdAssessment.assessment.id,
    headers: consultant.headers,
    answers: {
      target_process: "Qualifier les dossiers entrants avant affectation.",
      problem_statement:
        "Le tri manuel provoque des écarts de traitement entre les gestionnaires.",
      ai_task: "Le gestionnaire qualifie manuellement chaque dossier avant affectation.",
      primary_kpi: "Temps de qualification actuel",
      value_hypothesis: "Réduire les reprises manuelles grâce à une préqualification assistée.",
      risk_hypothesis:
        "La recommandation IA doit rester revue par un humain avant toute affectation.",
      missing_knowledge: "Seuil d’acceptation métier non documenté.",
    },
  });

  await selectDevIdentity(page, request, {
    subjectId: "consultant",
    displayName: "Local Consultant",
    role: "Consultant",
  });
  await openUseCase(page, bootstrap);

  await expect(page.getByText(KICKSTART_DISABLED_TEXT)).toBeVisible();
  await expect(
    page.getByRole("button", { name: GENERATE_KICKSTART_LABEL }),
  ).toHaveCount(0);

  const workspaceAfterEnable = await setWorkspaceAiAssistance(request, {
    workspaceId: bootstrap.workspaceId,
    headers: workspaceAdmin.headers,
    enabled: true,
    note: "Résumé métier approuvé pour tests S9, sans PII ni secret.",
  });
  expect(workspaceAfterEnable.ai_assistance_enabled).toBe(true);
  expect(workspaceAfterEnable.ai_assistance_available).toBe(true);
  expect(workspaceAfterEnable.ai_assistance_consent_at).toBeTruthy();
  expect(workspaceAfterEnable.ai_assistance_data_processing_note).toContain(
    "tests S9",
  );

  await page.reload();
  await openUseCase(page, bootstrap);
  await expect(
    page.getByRole("button", { name: GENERATE_KICKSTART_LABEL }),
  ).toBeVisible();
  const kickstartResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "POST" &&
      url.pathname ===
        `/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/assessments/${createdAssessment.assessment.id}/kickstart`
    );
  });
  await page.getByRole("button", { name: GENERATE_KICKSTART_LABEL }).click();
  const kickstartSuggestion = await expectApiJson<KickstartSuggestion>(
    await kickstartResponsePromise,
    "Generating AI kickstart proposal",
  );
  expect(kickstartSuggestion.provider).toBe("fake");
  expect(kickstartSuggestion.model).toBe("fake-kickstart-v1");

  const problemProposal = page.getByRole("textbox", {
    name: KICKSTART_PROBLEM_PROPOSAL_LABEL,
  });
  await expect(problemProposal).toHaveValue(
    kickstartSuggestion.proposal.problem_statement,
  );
  await problemProposal.fill(
    "Le tri initial reste hétérogène et rallonge la qualification des dossiers prioritaires.",
  );
  const problemCard = kickstartCard(page, KICKSTART_PROBLEM_HEADING);
  await problemCard
    .getByRole("button", { name: /Accepter cette proposition|Accept this proposal/ })
    .click();
  await expect(
    page.getByRole("heading", { name: KICKSTART_CONFIRM_TITLE }),
  ).toBeVisible();
  const overwriteDialog = page.getByRole("dialog");
  await expect(
    overwriteDialog.getByText(
      "Le tri manuel provoque des écarts de traitement entre les gestionnaires.",
    ),
  ).toBeVisible();
  await expect(
    overwriteDialog.getByText(
      "Le tri initial reste hétérogène et rallonge la qualification des dossiers prioritaires.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: KICKSTART_CONFIRM_BUTTON }).click();
  await expect(page.getByText(KICKSTART_APPLIED_TEXT)).toBeVisible();
  await expect(problemCard.getByText(AI_ASSISTED_TEXT)).toBeVisible();

  const kpiProposal = page.getByRole("textbox", {
    name: KICKSTART_KPI_PROPOSAL_LABEL,
  });
  await expect(kpiProposal).toHaveValue(
    kickstartSuggestion.proposal.kpi_proposals.join("\n"),
  );
  const kpiCard = kickstartCard(page, KICKSTART_KPI_HEADING);
  await kpiCard
    .getByRole("button", { name: /Accepter cette proposition|Accept this proposal/ })
    .click();
  await expect(
    page.getByRole("heading", { name: KICKSTART_CONFIRM_TITLE }),
  ).toBeVisible();
  await expect(overwriteDialog.getByText("Temps de qualification actuel")).toBeVisible();
  await expect(
    overwriteDialog.getByText(
      kickstartSuggestion.proposal.kpi_proposals.join("; "),
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: KICKSTART_CONFIRM_BUTTON }).click();
  await expect(kpiCard.getByText(KICKSTART_APPLIED_TEXT)).toBeVisible();

  const risksCard = kickstartCard(page, KICKSTART_RISKS_HEADING);
  await risksCard
    .getByRole("button", { name: /Ignorer|Ignore/ })
    .click();
  await expect(risksCard.getByText(KICKSTART_IGNORED_TEXT)).toBeVisible();

  const assessmentResponse = await request.get(
    `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/assessments/current`,
    {
      headers: consultant.headers,
    },
  );
  const assessmentBody = await expectApiJson<{
    template: {
      steps: Array<{
        questions: Array<{
          key: string;
          value: string | null;
          source: "human" | "ai_assisted" | null;
        }>;
      }>;
    };
  }>(assessmentResponse, "Fetching AI-assisted assessment");
  const questions = assessmentBody.template.steps.flatMap((step) => step.questions);
  expect(
    questions.find((question) => question.key === "problem_statement"),
  ).toMatchObject({
    value:
      "Le tri initial reste hétérogène et rallonge la qualification des dossiers prioritaires.",
    source: "ai_assisted",
  });
  expect(questions.find((question) => question.key === "primary_kpi")).toMatchObject({
    value: kickstartSuggestion.proposal.kpi_proposals.join("; "),
    source: "ai_assisted",
  });
  expect(questions.find((question) => question.key === "risk_hypothesis")).toMatchObject({
    value:
      "La recommandation IA doit rester revue par un humain avant toute affectation.",
    source: "human",
  });
});

test("routes sponsor approval through the review panel and inbox", async ({
  page,
  request,
}) => {
  const bootstrap = await bootstrapUseCase(request, {
    programName: `Programme review ${Date.now()}`,
    useCaseTitle: `Cas review ${Date.now()}`,
  });
  await proxyApiRequests(page, request);
  const consultant = await fetchDevIdentityHeaders(request, {
    subjectId: "consultant",
    displayName: "Local Consultant",
    role: "Consultant",
  });
  const sponsor = await fetchDevIdentityHeaders(request, {
    subjectId: "sponsor",
    displayName: "Local Sponsor",
    role: "Sponsor",
  });
  await selectDevIdentity(page, request, {
    subjectId: "consultant",
    displayName: "Local Consultant",
    role: "Consultant",
  });

  await openUseCase(page, bootstrap);
  await completeAndSubmitWizard(page);
  const assessmentResponse = await request.put(
    `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/value-assessment`,
    {
      headers: consultant.headers,
      data: {
        annual_volume: 12000,
        time_saved_hours: 0.2,
        hourly_cost: 45,
        error_reduction_rate: 20,
        average_error_cost: 85,
        revenue_capacity_value: 15000,
        estimated_annual_cost: 25000,
        time_to_impact_months: 4,
        primary_kpi: "Temps moyen de qualification",
        kpi_target: "-30%",
        confidence: "medium",
        currency: "EUR",
      },
    },
  );
  await expectApiOk(assessmentResponse, "Saving review value assessment");

  const recalculateResponse = await request.post(
    `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/scorecards/recalculate`,
    {
      headers: consultant.headers,
    },
  );
  await expectApiOk(recalculateResponse, "Recalculating review scorecard");
  await page
    .getByLabel(REVIEW_SUMMARY_LABEL)
    .fill(
      "Le pilote est cadré, les données sont accessibles et la validation humaine reste obligatoire.",
    );
  const reviewSummary =
    "Le pilote est cadré, les données sont accessibles et la validation humaine reste obligatoire.";
  await page
    .getByLabel(REVIEW_RISKS_LABEL)
    .fill("Complétude initiale des pièces\nStabilisation des règles métier");
  const reviewRisks = [
    "Complétude initiale des pièces",
    "Stabilisation des règles métier",
  ];
  await submitReviewAndWaitForPersistence(page, request, {
    bootstrap,
    headers: consultant.headers,
    summary: reviewSummary,
    risks: reviewRisks,
  });
  await expect(page.getByText("Complétude initiale des pièces")).toBeVisible();

  const markdownDocument = await request.post(
    `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/documents`,
    {
      headers: {
        ...consultant.headers,
        "Idempotency-Key": `pw-doc-markdown-${Date.now()}`,
      },
      data: {
        type: "PilotCharter",
        format: "markdown",
        language: "fr",
      },
    },
  );
  await expectApiOk(markdownDocument, "Generating markdown pilot charter");

  await selectDevIdentity(page, request, {
    subjectId: "sponsor",
    displayName: "Local Sponsor",
    role: "Sponsor",
  });
  await page.goto(`/studio/workspace?workspaceId=${bootstrap.workspaceId}`);
  await expect(
    page.getByRole("heading", { name: REVIEW_INBOX_TITLE }),
  ).toBeVisible();
  await expect(page.getByText(bootstrap.useCaseId)).toHaveCount(0);
  await expect(page.getByText(/Cas review/)).toBeVisible();
  await page.getByRole("link", { name: OPEN_REVIEW_LINK }).click();

  await expect(
    page.getByRole("heading", { name: REVIEW_PANEL_TITLE }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: DOCUMENT_CENTRE_TITLE }),
  ).toBeVisible();
  const currentDownloadButton = page.getByRole("button", {
    name: /Télécharger la version courante de Charte pilote|Download current Pilot Charter/,
  });
  const approveDocumentButton = page.getByRole("button", {
    name: /Approuver la version courante de Charte pilote|Approve current Pilot Charter/,
  });
  await expect(currentDownloadButton).toHaveAttribute("aria-disabled", "true");
  await expect(currentDownloadButton).toHaveAttribute(
    "aria-describedby",
    /download-reason/,
  );
  await expect(
    page.locator("#document-PilotCharter-download-reason"),
  ).toBeVisible();
  await expect(approveDocumentButton).toHaveAttribute("aria-disabled", "true");
  await expect(approveDocumentButton).toHaveAttribute(
    "aria-describedby",
    /approve-reason/,
  );
  await expect(
    page.locator("#document-PilotCharter-approve-reason"),
  ).toBeVisible();
  await page
    .getByLabel(ADD_COMMENT_LABEL)
    .fill("Merci de confirmer la stratégie de mitigation documentaire.");
  await page.getByRole("button", { name: ADD_COMMENT_LABEL }).click();
  await expect(
    page.getByText(
      "Merci de confirmer la stratégie de mitigation documentaire.",
    ),
  ).toBeVisible();
  await page
    .getByLabel(DECISION_REASON_LABEL)
    .fill(
      "Le périmètre pilote, les contrôles humains et les garde-fous sont acceptés.",
    );
  await page.getByLabel(CONFIRM_DECISION_LABEL).check();
  await page.getByRole("button", { name: APPROVE_REVIEW_LABEL }).click();
  await expect(page.getByText(/Approuvé|Approved/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: DOCUMENT_CENTRE_TITLE }),
  ).toBeVisible();
  await expectNoTaggedAxeViolations(page);

  const generatedDocument = await request.post(
    `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/documents`,
    {
      headers: {
        ...consultant.headers,
        "Idempotency-Key": `pw-doc-${Date.now()}`,
      },
      data: {
        type: "PilotCharter",
        format: "pdf",
        language: "fr",
      },
    },
  );
  const generatedBody = await expectApiJson<{
    id: string;
    current_version: { id: string; sha256: string; format: string };
  }>(generatedDocument, "Generating PDF pilot charter");
  await page.reload();

  const currentApproveButton = page.getByRole("button", {
    name: /Approuver la version courante de Charte pilote|Approve current Pilot Charter/,
  });
  await expect(currentApproveButton).toBeVisible();
  await expect(currentApproveButton).not.toHaveAttribute(
    "aria-disabled",
    "true",
  );
  await currentApproveButton.click();
  await expect(
    page.getByText(/Document approuvé|Document approved/),
  ).toBeVisible();

  const currentApprovedDownloadButton = page.getByRole("button", {
    name: /Télécharger la version courante de Charte pilote|Download current Pilot Charter/,
  });
  await expect(currentApprovedDownloadButton).not.toHaveAttribute(
    "aria-disabled",
    "true",
  );
  const [browserDownload] = await Promise.all([
    page.waitForEvent("download"),
    currentApprovedDownloadButton.click(),
  ]);
  expect(browserDownload.suggestedFilename()).toMatch(/\.pdf$/i);
  const browserDownloadPath = `test-results/document-centre-${Date.now()}.pdf`;
  await browserDownload.saveAs(browserDownloadPath);
  expect((await readFile(browserDownloadPath)).subarray(0, 4).toString()).toBe(
    "%PDF",
  );

  const approvedDocument = await request.get(
    `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/documents`,
    {
      headers: sponsor.headers,
    },
  );
  const approvedDocumentsBody = await expectApiJson<
    Array<{
      id: string;
      current_version: { id: string } | null;
      type: string;
    }>
  >(approvedDocument, "Fetching approved documents");
  const approvedPilotCharter = approvedDocumentsBody.find(
    (document) => document.type === "PilotCharter",
  );
  expect(approvedPilotCharter?.id).toBe(generatedBody.id);

  const download = await request.get(
    `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/document-versions/${generatedBody.current_version.id}/download`,
    {
      headers: sponsor.headers,
    },
  );
  expect(download.ok()).toBeTruthy();
  expect(download.headers()["content-type"]).toBe("application/pdf");
  expect(download.headers()["x-document-sha256"]).toBe(
    generatedBody.current_version.sha256,
  );
  expect((await download.body()).subarray(0, 4).toString()).toBe("%PDF");
});

test("renders a populated portfolio matrix, filters it, and passes axe smoke", async ({
  page,
  request,
}) => {
  await proxyApiRequests(page, request);
  const consultant = await fetchDevIdentityHeaders(request, {
    subjectId: "consultant",
    displayName: "Local Consultant",
    role: "Consultant",
  });
  const portfolioTimestamp = Date.now();
  const firstProgramName = `Programme portefeuille A ${portfolioTimestamp}`;
  const firstUseCaseTitle = `Cas portefeuille A ${portfolioTimestamp}`;
  const secondProgramName = `Programme portefeuille B ${portfolioTimestamp}`;
  const secondUseCaseTitle = `Cas portefeuille B ${portfolioTimestamp}`;
  const firstBootstrap = await bootstrapUseCase(request, {
    programName: firstProgramName,
    useCaseTitle: firstUseCaseTitle,
  });
  const secondBootstrap = await bootstrapUseCase(request, {
    programName: secondProgramName,
    useCaseTitle: secondUseCaseTitle,
  });

  await selectDevIdentity(page, request, {
    subjectId: "consultant",
    displayName: "Local Consultant",
    role: "Consultant",
  });

  await seedScorecardSnapshot(page, request, {
    bootstrap: firstBootstrap,
    consultantHeaders: consultant.headers,
    revenueCapacityValue: 15000,
  });
  await seedScorecardSnapshot(page, request, {
    bootstrap: secondBootstrap,
    consultantHeaders: consultant.headers,
    revenueCapacityValue: 45000,
  });

  await page.goto(`/studio/portfolio?workspaceId=${firstBootstrap.workspaceId}`);
  await expect(page.getByRole("heading", { name: PORTFOLIO_TITLE })).toBeVisible();
  await expect(page.getByText(firstBootstrap.useCaseId)).toHaveCount(0);
  await expect(page.getByRole("button", { name: new RegExp(firstUseCaseTitle) })).toBeVisible();
  await expect(page.getByRole("button", { name: new RegExp(secondUseCaseTitle) })).toBeVisible();
  await expectNoTaggedAxeViolations(page);

  await page.getByRole("button", { name: PORTFOLIO_TABLE_VIEW }).click();
  await expect(page.getByRole("table")).toBeVisible();
  await page.getByLabel(PORTFOLIO_PROGRAM_FILTER).selectOption(secondBootstrap.programId);
  await expect(page.getByRole("button", { name: secondUseCaseTitle, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: firstUseCaseTitle, exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: PORTFOLIO_MATRIX_VIEW }).click();
  await expect(page.getByRole("link", { name: /Ouvrir le cas d’usage|Open use case/ }).last()).toBeVisible();
  await expectNoTaggedAxeViolations(page);
});

test("supports the changes-request loop before creating a new draft version", async ({
  page,
  request,
}) => {
  const consultant = await fetchDevIdentityHeaders(request, {
    subjectId: "consultant",
    displayName: "Local Consultant",
    role: "Consultant",
  });
  const bootstrap = await bootstrapUseCase(request, {
    programName: `Programme changes ${Date.now()}`,
    useCaseTitle: `Cas changes ${Date.now()}`,
  });
  await proxyApiRequests(page, request);
  await selectDevIdentity(page, request, {
    subjectId: "consultant",
    displayName: "Local Consultant",
    role: "Consultant",
  });

  await openUseCase(page, bootstrap);
  await completeAndSubmitWizard(page);
  await page
    .getByLabel(REVIEW_SUMMARY_LABEL)
    .fill(
      "Le dossier est prêt pour revue, sous réserve d’un dernier cadrage des contrôles documentaires.",
    );
  const reviewSummary =
    "Le dossier est prêt pour revue, sous réserve d’un dernier cadrage des contrôles documentaires.";
  await page
    .getByLabel(REVIEW_RISKS_LABEL)
    .fill("Clarifier les règles sur les pièces manquantes");
  await submitReviewAndWaitForPersistence(page, request, {
    bootstrap,
    headers: consultant.headers,
    summary: reviewSummary,
    risks: ["Clarifier les règles sur les pièces manquantes"],
  });

  await selectDevIdentity(page, request, {
    subjectId: "sponsor",
    displayName: "Local Sponsor",
    role: "Sponsor",
  });
  await openUseCase(page, bootstrap);
  await page
    .getByLabel(DECISION_REASON_LABEL)
    .fill("Préciser les garde-fous de qualité documentaire avant approbation.");
  await page.getByLabel(CONFIRM_DECISION_LABEL).check();
  await page.getByRole("button", { name: REQUEST_CHANGES_LABEL }).click();
  await expect(
    page.getByText(/Révisions demandées|Changes requested/),
  ).toBeVisible();

  await selectDevIdentity(page, request, {
    subjectId: "consultant",
    displayName: "Local Consultant",
    role: "Consultant",
  });
  await page.goto(`/studio/workspace?workspaceId=${bootstrap.workspaceId}`);
  await expect(
    page.getByRole("heading", { name: REVIEW_INBOX_TITLE }),
  ).toBeVisible();
  await expect(
    page.getByText(/Révisions demandées|Changes requested/),
  ).toBeVisible();

  await openUseCase(page, bootstrap);
  await expect(
    page.getByRole("button", { name: NEW_DRAFT_LABEL }),
  ).toBeVisible();
  await page.getByRole("button", { name: NEW_DRAFT_LABEL }).click();
  await expect(
    page.getByRole("heading", { name: PREVIOUS_CYCLES_TITLE }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Préciser les garde-fous de qualité documentaire avant approbation.",
    ),
  ).toBeVisible();
  await expect(page.getByLabel("Processus cible")).toHaveValue(
    "Qualifier les dossiers entrants avant affectation.",
  );
  await expect(page.getByLabel("Processus cible")).toBeEnabled();
  for (let index = 0; index < 7; index += 1) {
    await page.getByRole("button", { name: CONTINUE_LABEL }).click();
  }
  await expect(
    page.getByRole("heading", { name: REVIEW_HEADING }),
  ).toBeVisible();
  await page.getByRole("button", { name: SUBMIT_LABEL }).click();
  await page
    .getByLabel(REVIEW_SUMMARY_LABEL)
    .fill(
      "La version 2 précise les contrôles documentaires et conserve la validation humaine.",
    );
  const updatedReviewSummary =
    "La version 2 précise les contrôles documentaires et conserve la validation humaine.";
  await page
    .getByLabel(REVIEW_RISKS_LABEL)
    .fill("Confirmer la tenue de charge sur le pilote");
  await submitReviewAndWaitForPersistence(page, request, {
    bootstrap,
    headers: consultant.headers,
    summary: updatedReviewSummary,
    risks: ["Confirmer la tenue de charge sur le pilote"],
  });

  await selectDevIdentity(page, request, {
    subjectId: "sponsor",
    displayName: "Local Sponsor",
    role: "Sponsor",
  });
  await openUseCase(page, bootstrap);
  await expect(
    page.getByRole("heading", { name: PREVIOUS_CYCLES_TITLE }),
  ).toBeVisible();
  await page
    .getByLabel(DECISION_REASON_LABEL)
    .fill(
      "Les précisions apportées sur la qualité documentaire sont suffisantes.",
    );
  await page.getByLabel(CONFIRM_DECISION_LABEL).check();
  await page.getByRole("button", { name: APPROVE_REVIEW_LABEL }).click();
  await expect(page.getByText(/Approuvé|Approved/)).toBeVisible();
  await expectNoTaggedAxeViolations(page);
});

test("keeps offline edits across reload and persists them after retrying online", async ({
  page,
  request,
}) => {
  const bootstrap = await bootstrapUseCase(request, {
    programName: `Programme offline ${Date.now()}`,
    useCaseTitle: `Cas offline ${Date.now()}`,
  });
  const apiProxy = await proxyApiRequests(page, request);
  const workspaceAdmin = await fetchDevIdentityHeaders(request, {
    subjectId: "workspace-admin",
    displayName: "Local Workspace Admin",
    role: "WorkspaceAdmin",
  });
  await selectDevIdentity(page, request, {
    subjectId: "workspace-admin",
    displayName: "Local Workspace Admin",
    role: "WorkspaceAdmin",
  });

  await openUseCase(page, bootstrap);
  await page.getByRole("button", { name: CREATE_DRAFT_LABEL }).click();
  await page
    .getByLabel("Processus cible")
    .fill("Qualification initiale fiable.");
  await expect(page.getByText(SAVED_AT_TEXT)).toBeVisible({ timeout: 10_000 });

  apiProxy.goOffline();
  await page.getByLabel("Équipe concernée").fill("Équipe hors ligne");
  await expect(
    page.getByRole("button", { name: /Réessayer|Retry/ }),
  ).toBeVisible({
    timeout: 10_000,
  });
  await expect(page.getByText(SAVED_AT_TEXT)).toHaveCount(0);

  await page.reload();
  await openUseCase(page, bootstrap);
  await expect(page.getByLabel("Équipe concernée")).toHaveValue(
    "Équipe hors ligne",
  );
  await expect(
    page.getByRole("button", { name: /Réessayer|Retry/ }),
  ).toBeVisible();
  await expect(page.getByText(SAVED_AT_TEXT)).toHaveCount(0);

  apiProxy.goOnline();
  await page.getByRole("button", { name: /Réessayer|Retry/ }).click();
  await expect(page.getByText(SAVED_AT_TEXT)).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByRole("button", { name: /Réessayer|Retry/ }),
  ).toHaveCount(0);

  const assessmentResponse = await request.get(
    `http://127.0.0.1:8010/api/v1/workspaces/${bootstrap.workspaceId}/programs/${bootstrap.programId}/use-cases/${bootstrap.useCaseId}/assessments/current`,
    {
      headers: workspaceAdmin.headers,
    },
  );
  expect(assessmentResponse.ok()).toBeTruthy();
  const assessment = (await assessmentResponse.json()) as {
    template: {
      steps: Array<{ questions: Array<{ key: string; value: string | null }> }>;
    };
  };
  const teamName = assessment.template.steps
    .flatMap((step) => step.questions)
    .find((question) => question.key === "team_name")?.value;
  expect(teamName).toBe("Équipe hors ligne");
});

test("shows actionable validation on missing required fields", async ({
  page,
  request,
}) => {
  const bootstrap = await bootstrapUseCase(request, {
    programName: `Programme invalid ${Date.now()}`,
    useCaseTitle: `Cas invalid ${Date.now()}`,
  });
  await proxyApiRequests(page, request);
  await selectDevIdentity(page, request, {
    subjectId: "workspace-admin",
    displayName: "Local Workspace Admin",
    role: "WorkspaceAdmin",
  });

  await openUseCase(page, bootstrap);
  await page.getByRole("button", { name: CREATE_DRAFT_LABEL }).click();
  await page.getByRole("button", { name: CONTINUE_LABEL }).click();

  await expect(page.getByText(MISSING_INFORMATION_TEXT).first()).toBeVisible();
  await expect(
    page.getByText("Ce champ est obligatoire.").first(),
  ).toBeVisible();
  await expect(page.getByLabel("Processus cible")).toBeFocused();
});

test("enforces contributor restrictions and supports interview attribution flow", async ({
  page,
  request,
}) => {
  const bootstrap = await bootstrapUseCase(request, {
    programName: `Programme contrib ${Date.now()}`,
    useCaseTitle: `Cas contrib ${Date.now()}`,
  });
  await proxyApiRequests(page, request);
  await selectDevIdentity(page, request, {
    subjectId: "workspace-admin",
    displayName: "Local Workspace Admin",
    role: "WorkspaceAdmin",
  });

  await openUseCase(page, bootstrap);
  await page.getByRole("button", { name: CREATE_DRAFT_LABEL }).click();
  await page.getByLabel(INTERVIEW_MODE_LABEL).click();
  await expect(page.getByLabel(RESPONDENT_LABEL)).toBeEnabled();
  await page
    .getByLabel(RESPONDENT_LABEL)
    .selectOption({ label: "Local Contributor" });
  await expect(page.getByText(INTERVIEW_ACTIVE_TEXT)).toBeVisible();
  await page
    .getByLabel("Processus cible")
    .fill("Qualification initiale en entretien.");
  await expect(page.getByText(SAVED_AT_TEXT)).toBeVisible({ timeout: 10_000 });

  await selectDevIdentity(page, request, {
    subjectId: "contributor",
    displayName: "Local Contributor",
    role: "Contributor",
  });
  await openUseCase(page, bootstrap);
  await expect(page.getByLabel("Processus cible")).toHaveValue(
    "Qualification initiale en entretien.",
  );
  await page.getByRole("button", { name: /4.*Valeur métier/ }).click();
  await expect(
    page.getByLabel("Temps gagné par transaction (heures)"),
  ).toBeDisabled();
  await page.getByRole("button", { name: /1.*Contexte et processus/ }).click();
  await page.getByLabel("Équipe concernée").fill("Contributeur local");
  await expect(
    page.getByText(
      "Only a consultant or workspace administrator can capture answers for someone else.",
    ),
  ).toBeVisible({ timeout: 10_000 });
});
