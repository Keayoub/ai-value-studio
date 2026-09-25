"use client";

import { useEffect, useMemo, useState } from "react";

type Lang = "fr" | "en";
type Vertical = "generic" | "health" | "insurance" | "hr" | "public" | "finance";
type FieldKind = "text" | "number" | "select";

type Question = {
  id: string;
  kind: FieldKind;
  label: Record<Lang, string>;
  help?: Record<Lang, string>;
  options?: { value: string; label: Record<Lang, string> }[];
  placeholder?: Record<Lang, string>;
};

type BvaInputs = {
  monthlyVolume: string;
  currentMinutes: string;
  targetMinutes: string;
  hourlyCost: string;
  currentErrorRate: string;
  targetErrorRate: string;
  errorCost: string;
  revenueCapacityValue: string;
  annualSolutionCost: string;
};

type WizardState = {
  organization: string;
  sponsor: string;
  strategicObjective: string;
  targetProcess: string;
  currentFriction: string;
  impactedDepartment: string;
  criticalConstraints: string;
  useCaseTitle: string;
  vertical: Vertical;
  dynamicAnswers: Record<string, string>;
  generatedProblem: string;
  generatedSolution: string;
  hypotheses: string[];
  recommendations: string[];
  bva: BvaInputs;
  reviewNotes: string;
};

const STORAGE_KEY = "ai-value-studio-wizard-v2";

const defaultState: WizardState = {
  organization: "",
  sponsor: "",
  strategicObjective: "",
  targetProcess: "",
  currentFriction: "",
  impactedDepartment: "",
  criticalConstraints: "",
  useCaseTitle: "",
  vertical: "generic",
  dynamicAnswers: {},
  generatedProblem: "",
  generatedSolution: "",
  hypotheses: [],
  recommendations: [],
  bva: {
    monthlyVolume: "",
    currentMinutes: "",
    targetMinutes: "",
    hourlyCost: "",
    currentErrorRate: "",
    targetErrorRate: "",
    errorCost: "",
    revenueCapacityValue: "",
    annualSolutionCost: "",
  },
  reviewNotes: "",
};

const content = {
  fr: {
    title: "TIFINIA AI Value Studio",
    subtitle:
      "Wizard AMOA IA intelligent pour identifier le besoin client, sélectionner le meilleur use case AI et générer un document AMOA + BVA complet.",
    stepTitles: [
      "Kickstart contexte",
      "Questionnaire dynamique",
      "Recommandations & hypothèses",
      "BVA (Business Value Assessment)",
      "Revue & document AMOA",
    ],
    verticalLabel: "Vertical métier",
    verticals: {
      generic: "Générique",
      health: "Santé",
      insurance: "Assurance / Mutuelle",
      hr: "RH / Talent",
      public: "Secteur public",
      finance: "Finance / Compliance",
    },
    actions: {
      prev: "Précédent",
      next: "Continuer",
      save: "Sauvegarder",
      runKickstart: "Lancer Kickstart IA",
      inferReco: "Générer recommandations",
      generateDoc: "Générer document AMOA + BVA",
      download: "Télécharger .md",
    },
    notices: {
      saved: "Brouillon sauvegardé localement.",
      kickstartDone: "Brouillon IA généré. Tu peux tout éditer avant de continuer.",
      recoDone: "Recommandations et hypothèses générées.",
    },
    labels: {
      organization: "Organisation client",
      sponsor: "Sponsor",
      strategicObjective: "Objectif stratégique",
      targetProcess: "Processus cible",
      currentFriction: "Friction principale",
      impactedDepartment: "Département impacté",
      criticalConstraints: "Contraintes critiques",
      useCaseTitle: "Titre du use case retenu",
      generatedProblem: "Problem statement proposé",
      generatedSolution: "Solution IA proposée",
      reviewNotes: "Notes de revue / décisions",
    },
  },
  en: {
    title: "TIFINIA AI Value Studio",
    subtitle:
      "Intelligent AI-advisory wizard to identify client needs, select the best-fit AI use case, and generate a complete AMOA + BVA document.",
    stepTitles: [
      "Context kickstart",
      "Dynamic questionnaire",
      "Recommendations & hypotheses",
      "BVA (Business Value Assessment)",
      "Review & AMOA document",
    ],
    verticalLabel: "Business vertical",
    verticals: {
      generic: "Generic",
      health: "Healthcare",
      insurance: "Insurance / Mutual",
      hr: "HR / Talent",
      public: "Public sector",
      finance: "Finance / Compliance",
    },
    actions: {
      prev: "Previous",
      next: "Continue",
      save: "Save",
      runKickstart: "Run AI kickstart",
      inferReco: "Generate recommendations",
      generateDoc: "Generate AMOA + BVA document",
      download: "Download .md",
    },
    notices: {
      saved: "Draft saved locally.",
      kickstartDone: "AI draft generated. You can edit every section.",
      recoDone: "Recommendations and hypotheses generated.",
    },
    labels: {
      organization: "Client organization",
      sponsor: "Sponsor",
      strategicObjective: "Strategic objective",
      targetProcess: "Target process",
      currentFriction: "Main friction",
      impactedDepartment: "Impacted department",
      criticalConstraints: "Critical constraints",
      useCaseTitle: "Selected use-case title",
      generatedProblem: "Proposed problem statement",
      generatedSolution: "Proposed AI solution",
      reviewNotes: "Review notes / decisions",
    },
  },
} as const;

const coreQuestions: Question[] = [
  {
    id: "process_volume",
    kind: "number",
    label: { fr: "Volume mensuel du processus", en: "Monthly process volume" },
  },
  {
    id: "decision_impact",
    kind: "select",
    label: { fr: "Impact d'une mauvaise décision", en: "Impact of a wrong decision" },
    options: [
      { value: "low", label: { fr: "Faible", en: "Low" } },
      { value: "medium", label: { fr: "Moyen", en: "Medium" } },
      { value: "high", label: { fr: "Élevé", en: "High" } },
      { value: "critical", label: { fr: "Critique", en: "Critical" } },
    ],
  },
  {
    id: "data_quality",
    kind: "select",
    label: { fr: "Qualité des données actuelle", en: "Current data quality" },
    options: [
      { value: "low", label: { fr: "Faible", en: "Low" } },
      { value: "medium", label: { fr: "Moyenne", en: "Medium" } },
      { value: "high", label: { fr: "Élevée", en: "High" } },
    ],
  },
  {
    id: "human_validation",
    kind: "select",
    label: { fr: "Validation humaine requise ?", en: "Human validation required?" },
    options: [
      { value: "mandatory", label: { fr: "Obligatoire", en: "Mandatory" } },
      { value: "partial", label: { fr: "Partielle", en: "Partial" } },
      { value: "minimal", label: { fr: "Minimale", en: "Minimal" } },
    ],
  },
  {
    id: "kpi_target",
    kind: "text",
    label: { fr: "KPI principal ciblé", en: "Primary target KPI" },
    placeholder: { fr: "Ex: -30% délai de traitement", en: "e.g. -30% processing time" },
  },
];

const verticalQuestions: Record<Vertical, Question[]> = {
  generic: [
    {
      id: "integration_complexity",
      kind: "select",
      label: { fr: "Complexité d'intégration SI", en: "IS integration complexity" },
      options: [
        { value: "low", label: { fr: "Faible", en: "Low" } },
        { value: "medium", label: { fr: "Moyenne", en: "Medium" } },
        { value: "high", label: { fr: "Élevée", en: "High" } },
      ],
    },
  ],
  health: [
    {
      id: "health_case_type",
      kind: "text",
      label: { fr: "Type de dossier patient", en: "Patient case type" },
    },
    {
      id: "health_phi",
      kind: "select",
      label: { fr: "Présence de données médicales sensibles", en: "Sensitive medical data present" },
      options: [
        { value: "yes", label: { fr: "Oui", en: "Yes" } },
        { value: "no", label: { fr: "Non", en: "No" } },
      ],
    },
  ],
  insurance: [
    {
      id: "ins_claim_docs",
      kind: "number",
      label: { fr: "Nombre moyen de documents par dossier", en: "Average documents per case" },
    },
    {
      id: "ins_fraud_risk",
      kind: "select",
      label: { fr: "Risque de fraude", en: "Fraud risk" },
      options: [
        { value: "low", label: { fr: "Faible", en: "Low" } },
        { value: "medium", label: { fr: "Moyen", en: "Medium" } },
        { value: "high", label: { fr: "Élevé", en: "High" } },
      ],
    },
  ],
  hr: [
    {
      id: "hr_candidate_volume",
      kind: "number",
      label: { fr: "Candidatures mensuelles", en: "Monthly applications" },
    },
    {
      id: "hr_bias_risk",
      kind: "select",
      label: { fr: "Risque de biais décisionnel", en: "Decision-bias risk" },
      options: [
        { value: "low", label: { fr: "Faible", en: "Low" } },
        { value: "medium", label: { fr: "Moyen", en: "Medium" } },
        { value: "high", label: { fr: "Élevé", en: "High" } },
      ],
    },
  ],
  public: [
    {
      id: "public_regulatory",
      kind: "text",
      label: { fr: "Contraintes réglementaires clés", en: "Key regulatory constraints" },
    },
    {
      id: "public_sla",
      kind: "text",
      label: { fr: "SLA citoyen / service attendu", en: "Citizen SLA / expected service level" },
    },
  ],
  finance: [
    {
      id: "fin_auditability",
      kind: "select",
      label: { fr: "Niveau d'auditabilité exigé", en: "Required auditability level" },
      options: [
        { value: "standard", label: { fr: "Standard", en: "Standard" } },
        { value: "strict", label: { fr: "Strict", en: "Strict" } },
      ],
    },
    {
      id: "fin_approval",
      kind: "text",
      label: { fr: "Étapes d'approbation manuelle", en: "Manual approval steps" },
    },
  ],
};

function loadInitialState(): WizardState {
  if (typeof window === "undefined") {
    return defaultState;
  }

  const saved = window.localStorage.getItem(STORAGE_KEY);
  if (!saved) {
    return defaultState;
  }

  try {
    return { ...defaultState, ...JSON.parse(saved) as WizardState };
  } catch {
    return defaultState;
  }
}

function toNumber(value: string): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function field(
  label: string,
  value: string,
  onChange: (v: string) => void,
  options?: { value: string; label: string }[],
  type: FieldKind = "text",
  placeholder?: string,
) {
  return (
    <label className="block space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      {type === "select" && options ? (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">--</option>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
          type={type === "number" ? "number" : "text"}
        />
      )}
    </label>
  );
}

export default function Home() {
  const [lang, setLang] = useState<Lang>("fr");
  const [step, setStep] = useState(0);
  const [state, setState] = useState<WizardState>(loadInitialState);
  const [notice, setNotice] = useState("");
  const [finalDoc, setFinalDoc] = useState("");

  const t = content[lang];

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const questions = useMemo(
    () => [...coreQuestions, ...verticalQuestions[state.vertical]],
    [state.vertical],
  );

  const progress = Math.round((step / 4) * 100);

  const bva = useMemo(() => {
    const annualVolume = toNumber(state.bva.monthlyVolume) * 12;
    const timeSavedHours = Math.max(0, (toNumber(state.bva.currentMinutes) - toNumber(state.bva.targetMinutes)) / 60);
    const annualTimeValue = annualVolume * timeSavedHours * toNumber(state.bva.hourlyCost);
    const errorReduction = Math.max(0, (toNumber(state.bva.currentErrorRate) - toNumber(state.bva.targetErrorRate)) / 100);
    const errorAvoidanceValue = annualVolume * errorReduction * toNumber(state.bva.errorCost);
    const gross = annualTimeValue + errorAvoidanceValue + toNumber(state.bva.revenueCapacityValue);
    const net = gross - toNumber(state.bva.annualSolutionCost);

    return { annualVolume, annualTimeValue, errorAvoidanceValue, gross, net };
  }, [state.bva]);

  const runKickstart = () => {
    const generatedProblem =
      lang === "fr"
        ? `Le processus "${state.targetProcess || "N/A"}" crée une friction majeure (${state.currentFriction || "N/A"}) pour ${state.impactedDepartment || "l'équipe concernée"}.`
        : `The process "${state.targetProcess || "N/A"}" creates major friction (${state.currentFriction || "N/A"}) for ${state.impactedDepartment || "the concerned team"}.`;

    const generatedSolution =
      lang === "fr"
        ? "Mettre en place un assistant IA supervisé orienté qualification, recommandation et validation humaine obligatoire."
        : "Deploy a supervised AI assistant focused on qualification, recommendation, and mandatory human validation.";

    const hypotheses =
      lang === "fr"
        ? [
            "Réduction de 20 à 40% du temps de traitement",
            "Réduction du coût des erreurs critiques",
            "Amélioration de la conformité et traçabilité",
          ]
        : [
            "20-40% processing-time reduction",
            "Lower cost of critical errors",
            "Improved compliance and traceability",
          ];

    setState((prev) => ({ ...prev, generatedProblem, generatedSolution, hypotheses }));
    setNotice(t.notices.kickstartDone);
  };

  const inferRecommendations = () => {
    const recos: string[] = [];
    const dataQuality = state.dynamicAnswers.data_quality;
    const impact = state.dynamicAnswers.decision_impact;
    const human = state.dynamicAnswers.human_validation;

    if (dataQuality === "low") {
      recos.push(
        lang === "fr"
          ? "Lancer un mini chantier data foundation avant le pilote (qualité + dictionnaire de données)."
          : "Run a data-foundation mini-workstream before the pilot (quality + data dictionary).",
      );
    }

    if (impact === "high" || impact === "critical") {
      recos.push(
        lang === "fr"
          ? "Forcer un contrôle humain sur les décisions à impact et tracer les justifications."
          : "Enforce human review on high-impact decisions and log justifications.",
      );
    }

    if (human === "mandatory") {
      recos.push(
        lang === "fr"
          ? "Concevoir un workflow HITL avec seuils d'escalade explicites."
          : "Design a HITL workflow with explicit escalation thresholds.",
      );
    }

    recos.push(
      lang === "fr"
        ? "Démarrer par un pilote 6-8 semaines sur un périmètre mesurable avant scale."
        : "Start with a measurable 6-8 week pilot scope before scale.",
    );

    setState((prev) => ({ ...prev, recommendations: recos }));
    setNotice(t.notices.recoDone);
  };

  const generateFinalDocument = () => {
    const dynamicRows = questions
      .map((q) => {
        const answer = state.dynamicAnswers[q.id] || "N/A";
        return `- ${q.label[lang]}: ${answer}`;
      })
      .join("\n");

    const recoRows = (state.recommendations.length ? state.recommendations : ["N/A"])
      .map((r) => `- ${r}`)
      .join("\n");

    const hypoRows = (state.hypotheses.length ? state.hypotheses : ["N/A"])
      .map((h) => `- ${h}`)
      .join("\n");

    const date = new Date().toISOString().slice(0, 10);

    const doc = lang === "fr"
      ? `# Document AMOA + BVA — ${state.useCaseTitle || "Use case"}

## 1) Contexte client
- Date: ${date}
- Organisation: ${state.organization || "N/A"}
- Sponsor: ${state.sponsor || "N/A"}
- Vertical: ${t.verticals[state.vertical]}
- Objectif stratégique: ${state.strategicObjective || "N/A"}

## 2) Besoin et use case cible
- Processus cible: ${state.targetProcess || "N/A"}
- Friction principale: ${state.currentFriction || "N/A"}
- Department impacté: ${state.impactedDepartment || "N/A"}
- Contraintes critiques: ${state.criticalConstraints || "N/A"}
- Problem statement: ${state.generatedProblem || "N/A"}
- Solution IA proposée: ${state.generatedSolution || "N/A"}

## 3) Questionnaire dynamique (adapté vertical)
${dynamicRows}

## 4) Recommandations et hypothèses
### Recommandations
${recoRows}

### Hypothèses
${hypoRows}

## 5) BVA (Business Value Assessment)
- Annual volume: ${bva.annualVolume.toFixed(0)}
- Annual Time Value: ${bva.annualTimeValue.toFixed(2)}
- Error Avoidance Value: ${bva.errorAvoidanceValue.toFixed(2)}
- Estimated Gross Value: ${bva.gross.toFixed(2)}
- Estimated Net Value: ${bva.net.toFixed(2)}

## 6) Plan de mise en place
- Phase 1 (S1-S2): Cadrage détaillé + data readiness
- Phase 2 (S3-S6): Pilot build + validation humaine
- Phase 3 (S7-S8): Mesure KPI + décision Go/No-Go

## 7) Gouvernance
- Validation humaine: ${state.dynamicAnswers.human_validation || "N/A"}
- Notes de revue: ${state.reviewNotes || "N/A"}
`
      : `# AMOA + BVA Document — ${state.useCaseTitle || "Use case"}

## 1) Client context
- Date: ${date}
- Organization: ${state.organization || "N/A"}
- Sponsor: ${state.sponsor || "N/A"}
- Vertical: ${t.verticals[state.vertical]}
- Strategic objective: ${state.strategicObjective || "N/A"}

## 2) Need and target use case
- Target process: ${state.targetProcess || "N/A"}
- Main friction: ${state.currentFriction || "N/A"}
- Impacted department: ${state.impactedDepartment || "N/A"}
- Critical constraints: ${state.criticalConstraints || "N/A"}
- Problem statement: ${state.generatedProblem || "N/A"}
- Proposed AI solution: ${state.generatedSolution || "N/A"}

## 3) Dynamic questionnaire (vertical-adapted)
${dynamicRows}

## 4) Recommendations and hypotheses
### Recommendations
${recoRows}

### Hypotheses
${hypoRows}

## 5) BVA (Business Value Assessment)
- Annual volume: ${bva.annualVolume.toFixed(0)}
- Annual Time Value: ${bva.annualTimeValue.toFixed(2)}
- Error Avoidance Value: ${bva.errorAvoidanceValue.toFixed(2)}
- Estimated Gross Value: ${bva.gross.toFixed(2)}
- Estimated Net Value: ${bva.net.toFixed(2)}

## 6) Implementation plan
- Phase 1 (W1-W2): Detailed framing + data readiness
- Phase 2 (W3-W6): Pilot build + human validation
- Phase 3 (W7-W8): KPI measurement + Go/No-Go decision

## 7) Governance
- Human validation: ${state.dynamicAnswers.human_validation || "N/A"}
- Review notes: ${state.reviewNotes || "N/A"}
`;

    setFinalDoc(doc);
  };

  const downloadDocument = () => {
    if (!finalDoc) return;
    const blob = new Blob([finalDoc], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = lang === "fr" ? "amoa_bva_fr.md" : "amoa_bva_en.md";
    a.click();
    URL.revokeObjectURL(url);
  };

  const setAnswer = (id: string, value: string) => {
    setState((prev) => ({ ...prev, dynamicAnswers: { ...prev.dynamicAnswers, [id]: value } }));
    setNotice("");
  };

  const setBvaField = (key: keyof BvaInputs, value: string) => {
    setState((prev) => ({ ...prev, bva: { ...prev.bva, [key]: value } }));
    setNotice("");
  };

  const saveDraft = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    setNotice(t.notices.saved);
  };

  return (
    <main className="min-h-screen bg-slate-50 p-6 md:p-10">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-black/5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold">{t.title}</h1>
              <p className="mt-1 text-sm text-slate-600">{t.subtitle}</p>
            </div>
            <div className="flex rounded-xl border border-black/10 p-1">
              <button
                className={`rounded-lg px-3 py-1 text-sm ${lang === "fr" ? "bg-black text-white" : "text-black"}`}
                onClick={() => setLang("fr")}
              >
                FR
              </button>
              <button
                className={`rounded-lg px-3 py-1 text-sm ${lang === "en" ? "bg-black text-white" : "text-black"}`}
                onClick={() => setLang("en")}
              >
                EN
              </button>
            </div>
          </div>

          <div className="mt-4">
            <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
              <span>{t.stepTitles[step]}</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 rounded-full bg-slate-200">
              <div className="h-2 rounded-full bg-indigo-600" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </header>

        <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-black/5 space-y-5">
          {step === 0 && (
            <>
              {field(t.labels.organization, state.organization, (v) => setState((p) => ({ ...p, organization: v })))}
              {field(t.labels.sponsor, state.sponsor, (v) => setState((p) => ({ ...p, sponsor: v })))}
              {field(t.labels.strategicObjective, state.strategicObjective, (v) => setState((p) => ({ ...p, strategicObjective: v })))}
              {field(t.labels.targetProcess, state.targetProcess, (v) => setState((p) => ({ ...p, targetProcess: v })))}
              {field(t.labels.currentFriction, state.currentFriction, (v) => setState((p) => ({ ...p, currentFriction: v })))}
              {field(t.labels.impactedDepartment, state.impactedDepartment, (v) => setState((p) => ({ ...p, impactedDepartment: v })))}
              {field(t.labels.criticalConstraints, state.criticalConstraints, (v) => setState((p) => ({ ...p, criticalConstraints: v })))}
              {field(t.labels.useCaseTitle, state.useCaseTitle, (v) => setState((p) => ({ ...p, useCaseTitle: v })))}

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">{t.verticalLabel}</span>
                <select
                  value={state.vertical}
                  onChange={(e) => setState((p) => ({ ...p, vertical: e.target.value as Vertical }))}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  {(Object.keys(t.verticals) as Vertical[]).map((v) => (
                    <option key={v} value={v}>
                      {t.verticals[v]}
                    </option>
                  ))}
                </select>
              </label>

              <button onClick={runKickstart} className="rounded-xl bg-black px-4 py-2 text-sm text-white">
                {t.actions.runKickstart}
              </button>

              {field(t.labels.generatedProblem, state.generatedProblem, (v) => setState((p) => ({ ...p, generatedProblem: v })))}
              {field(t.labels.generatedSolution, state.generatedSolution, (v) => setState((p) => ({ ...p, generatedSolution: v })))}
            </>
          )}

          {step === 1 && (
            <div className="grid gap-4 md:grid-cols-2">
              {questions.map((q) =>
                field(
                  q.label[lang],
                  state.dynamicAnswers[q.id] || "",
                  (v) => setAnswer(q.id, v),
                  q.options?.map((o) => ({ value: o.value, label: o.label[lang] })),
                  q.kind,
                  q.placeholder?.[lang],
                ),
              )}
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <button onClick={inferRecommendations} className="rounded-xl bg-indigo-600 px-4 py-2 text-sm text-white">
                {t.actions.inferReco}
              </button>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-slate-200 p-4">
                  <h3 className="font-semibold">{lang === "fr" ? "Recommandations" : "Recommendations"}</h3>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                    {(state.recommendations.length ? state.recommendations : ["-"]).map((r, idx) => (
                      <li key={idx}>{r}</li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-xl border border-slate-200 p-4">
                  <h3 className="font-semibold">{lang === "fr" ? "Hypothèses" : "Hypotheses"}</h3>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                    {(state.hypotheses.length ? state.hypotheses : ["-"]).map((h, idx) => (
                      <li key={idx}>{h}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                {field(lang === "fr" ? "Volume mensuel" : "Monthly volume", state.bva.monthlyVolume, (v) => setBvaField("monthlyVolume", v), undefined, "number")}
                {field(lang === "fr" ? "Temps actuel (min)" : "Current time (min)", state.bva.currentMinutes, (v) => setBvaField("currentMinutes", v), undefined, "number")}
                {field(lang === "fr" ? "Temps cible (min)" : "Target time (min)", state.bva.targetMinutes, (v) => setBvaField("targetMinutes", v), undefined, "number")}
                {field(lang === "fr" ? "Coût horaire" : "Hourly cost", state.bva.hourlyCost, (v) => setBvaField("hourlyCost", v), undefined, "number")}
                {field(lang === "fr" ? "Taux erreur actuel (%)" : "Current error rate (%)", state.bva.currentErrorRate, (v) => setBvaField("currentErrorRate", v), undefined, "number")}
                {field(lang === "fr" ? "Taux erreur cible (%)" : "Target error rate (%)", state.bva.targetErrorRate, (v) => setBvaField("targetErrorRate", v), undefined, "number")}
                {field(lang === "fr" ? "Coût par erreur" : "Cost per error", state.bva.errorCost, (v) => setBvaField("errorCost", v), undefined, "number")}
                {field(lang === "fr" ? "Valeur capacité/revenu" : "Revenue/capacity value", state.bva.revenueCapacityValue, (v) => setBvaField("revenueCapacityValue", v), undefined, "number")}
                {field(lang === "fr" ? "Coût annuel solution" : "Annual solution cost", state.bva.annualSolutionCost, (v) => setBvaField("annualSolutionCost", v), undefined, "number")}
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
                <p>- Annual Volume: {bva.annualVolume.toFixed(0)}</p>
                <p>- Annual Time Value: {bva.annualTimeValue.toFixed(2)}</p>
                <p>- Error Avoidance Value: {bva.errorAvoidanceValue.toFixed(2)}</p>
                <p>- Estimated Gross Value: {bva.gross.toFixed(2)}</p>
                <p>- Estimated Net Value: {bva.net.toFixed(2)}</p>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4">
              {field(t.labels.reviewNotes, state.reviewNotes, (v) => setState((p) => ({ ...p, reviewNotes: v })))}
              <button onClick={generateFinalDocument} className="rounded-xl bg-indigo-600 px-4 py-2 text-sm text-white">
                {t.actions.generateDoc}
              </button>

              {finalDoc ? (
                <div className="space-y-2">
                  <pre className="max-h-96 overflow-auto rounded-xl border border-slate-200 bg-white p-3 text-xs">
                    {finalDoc}
                  </pre>
                  <button onClick={downloadDocument} className="rounded-xl border border-slate-300 px-4 py-2 text-sm">
                    {t.actions.download}
                  </button>
                </div>
              ) : null}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2 pt-2">
            <button
              onClick={() => setStep((s) => Math.max(0, s - 1))}
              className="rounded-xl border border-slate-300 px-4 py-2 text-sm"
            >
              {t.actions.prev}
            </button>
            <button
              onClick={saveDraft}
              className="rounded-xl border border-slate-300 px-4 py-2 text-sm"
            >
              {t.actions.save}
            </button>
            <button
              onClick={() => setStep((s) => Math.min(4, s + 1))}
              className="rounded-xl bg-black px-4 py-2 text-sm text-white"
            >
              {t.actions.next}
            </button>
          </div>

          {notice ? <p className="text-sm text-emerald-700">{notice}</p> : null}
        </section>
      </div>
    </main>
  );
}
