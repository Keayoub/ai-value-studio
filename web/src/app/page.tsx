"use client";

import { useEffect, useMemo, useState } from "react";

type Lang = "fr" | "en";

type WizardState = {
  strategicObjective: string;
  targetProcess: string;
  currentFriction: string;
  impactedDepartment: string;
  criticalConstraints: string;
  title: string;
  contextProcess: string;
  problem: string;
  aiSolution: string;
  businessValue: string;
  dataReadiness: string;
  technicalReadiness: string;
  riskGovernance: string;
  reviewNotes: string;
};

const STORAGE_KEY = "ai-value-studio-wizard-v1";

const defaultState: WizardState = {
  strategicObjective: "",
  targetProcess: "",
  currentFriction: "",
  impactedDepartment: "",
  criticalConstraints: "",
  title: "",
  contextProcess: "",
  problem: "",
  aiSolution: "",
  businessValue: "",
  dataReadiness: "",
  technicalReadiness: "",
  riskGovernance: "",
  reviewNotes: "",
};

const copy = {
  fr: {
    appTitle: "TIFINIA AI Value Studio",
    appSubtitle: "Framework AMOA IA bilingue pour cadrer, scorer et prioriser les use cases.",
    optionalKickstart: "Étape 0 (optionnelle) — Kickstart LLM",
    steps: [
      "Contexte & processus",
      "Problème & friction",
      "Solution IA",
      "Valeur business",
      "Data readiness",
      "Technical readiness",
      "Risk & governance",
      "Revue & soumission",
    ],
    labels: {
      strategicObjective: "Objectif stratégique",
      targetProcess: "Processus ciblé",
      currentFriction: "Friction actuelle",
      impactedDepartment: "Département impacté",
      criticalConstraints: "Contraintes critiques",
      title: "Titre du use case",
      contextProcess: "Description du processus",
      problem: "Problem statement",
      aiSolution: "Solution IA proposée",
      businessValue: "Hypothèses de valeur",
      dataReadiness: "État des données et gaps",
      technicalReadiness: "Readiness technique/opérationnelle",
      riskGovernance: "Risques & gouvernance",
      reviewNotes: "Notes de revue",
    },
    actions: {
      generateKickstart: "Générer brouillon LLM",
      previous: "Précédent",
      saveQuit: "Sauvegarder et quitter",
      next: "Continuer",
      generateAmoa: "Générer document AMOA de mise en place",
      download: "Télécharger .md",
    },
    done: "Brouillon généré (AI-assisted) — tu peux éditer chaque section.",
    amoaTitle: "Document AMOA généré",
    saveMsg: "Brouillon sauvegardé localement.",
  },
  en: {
    appTitle: "TIFINIA AI Value Studio",
    appSubtitle: "Bilingual AI advisory framework to structure, score, and prioritize use cases.",
    optionalKickstart: "Step 0 (optional) — LLM kickstart",
    steps: [
      "Context & process",
      "Problem & friction",
      "AI solution",
      "Business value",
      "Data readiness",
      "Technical readiness",
      "Risk & governance",
      "Review & submit",
    ],
    labels: {
      strategicObjective: "Strategic objective",
      targetProcess: "Target process",
      currentFriction: "Current friction",
      impactedDepartment: "Impacted department",
      criticalConstraints: "Critical constraints",
      title: "Use-case title",
      contextProcess: "Process description",
      problem: "Problem statement",
      aiSolution: "Proposed AI solution",
      businessValue: "Value hypotheses",
      dataReadiness: "Data readiness and gaps",
      technicalReadiness: "Technical/operational readiness",
      riskGovernance: "Risks & governance",
      reviewNotes: "Review notes",
    },
    actions: {
      generateKickstart: "Generate LLM draft",
      previous: "Previous",
      saveQuit: "Save and quit",
      next: "Continue",
      generateAmoa: "Generate AMOA implementation document",
      download: "Download .md",
    },
    done: "Draft generated (AI-assisted) — every section remains editable.",
    amoaTitle: "Generated AMOA document",
    saveMsg: "Draft saved locally.",
  },
} as const;

function textInput(
  label: string,
  value: string,
  onChange: (v: string) => void,
  rows = 3,
) {
  return (
    <label className="block space-y-2">
      <span className="text-sm font-medium">{label}</span>
      <textarea
        className="w-full rounded-xl border border-black/15 bg-white px-3 py-2 text-sm outline-none focus:border-black/40"
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

export default function Home() {
  const [lang, setLang] = useState<Lang>("fr");
  const [step, setStep] = useState(0);
  const [state, setState] = useState<WizardState>(defaultState);
  const [kickstartNotice, setKickstartNotice] = useState("");
  const [saveNotice, setSaveNotice] = useState("");
  const [amoaDocument, setAmoaDocument] = useState("");

  const t = copy[lang];

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as WizardState;
      setState({ ...defaultState, ...parsed });
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const progress = useMemo(() => Math.round((step / 8) * 100), [step]);

  const setField = (key: keyof WizardState, value: string) => {
    setState((prev) => ({ ...prev, [key]: value }));
    setKickstartNotice("");
    setSaveNotice("");
  };

  const runKickstart = () => {
    const problem =
      lang === "fr"
        ? `Le processus "${state.targetProcess || "N/A"}" crée une friction majeure (${state.currentFriction || "N/A"}) pour ${state.impactedDepartment || "l'équipe cible"}.`
        : `The process "${state.targetProcess || "N/A"}" creates major friction (${state.currentFriction || "N/A"}) for ${state.impactedDepartment || "the target team"}.`;

    const solution =
      lang === "fr"
        ? "Mettre en place un assistant IA supervisé pour structurer les entrées, recommander des actions et forcer une validation humaine sur les décisions sensibles."
        : "Deploy a supervised AI assistant to structure inputs, recommend actions, and enforce human approval for sensitive decisions.";

    const value =
      lang === "fr"
        ? "Hypothèse: réduction 20–40% du temps de traitement et baisse du coût des erreurs critiques."
        : "Hypothesis: 20–40% processing-time reduction and lower cost of critical errors.";

    const risk =
      lang === "fr"
        ? `Risque initial: ${state.criticalConstraints || "conformité / sécurité des données"}.`
        : `Initial risk: ${state.criticalConstraints || "compliance / data security"}.`;

    setState((prev) => ({
      ...prev,
      problem: prev.problem || problem,
      aiSolution: prev.aiSolution || solution,
      businessValue: prev.businessValue || value,
      riskGovernance: prev.riskGovernance || risk,
    }));

    setKickstartNotice(t.done);
  };

  const saveAndQuit = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    setSaveNotice(t.saveMsg);
  };

  const generateAmoa = () => {
    const date = new Date().toISOString().slice(0, 10);
    const doc = lang === "fr"
      ? `# AMOA Use Case Implementation Plan

## Métadonnées
- Date: ${date}
- Langue: FR
- Use case: ${state.title || "N/A"}

## 1) Cadrage métier
- Processus: ${state.contextProcess || "N/A"}
- Problème: ${state.problem || "N/A"}
- Solution IA: ${state.aiSolution || "N/A"}

## 2) Valeur business
${state.businessValue || "N/A"}

## 3) Data readiness
${state.dataReadiness || "N/A"}

## 4) Readiness technique
${state.technicalReadiness || "N/A"}

## 5) Risques & gouvernance
${state.riskGovernance || "N/A"}

## 6) Plan de mise en place
- Phase 1: Discovery & design
- Phase 2: Pilot build
- Phase 3: Go/No-Go & scale

## 7) Revue
${state.reviewNotes || "N/A"}
`
      : `# AMOA Use Case Implementation Plan

## Metadata
- Date: ${date}
- Language: EN
- Use case: ${state.title || "N/A"}

## 1) Business framing
- Process: ${state.contextProcess || "N/A"}
- Problem: ${state.problem || "N/A"}
- AI solution: ${state.aiSolution || "N/A"}

## 2) Business value
${state.businessValue || "N/A"}

## 3) Data readiness
${state.dataReadiness || "N/A"}

## 4) Technical readiness
${state.technicalReadiness || "N/A"}

## 5) Risk & governance
${state.riskGovernance || "N/A"}

## 6) Implementation plan
- Phase 1: Discovery & design
- Phase 2: Pilot build
- Phase 3: Go/No-Go & scale

## 7) Review
${state.reviewNotes || "N/A"}
`;

    setAmoaDocument(doc);
  };

  const downloadAmoa = () => {
    if (!amoaDocument) return;
    const blob = new Blob([amoaDocument], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = lang === "fr" ? "amoa_plan_fr.md" : "amoa_plan_en.md";
    a.click();
    URL.revokeObjectURL(url);
  };

  const wizardBody = () => {
    switch (step) {
      case 0:
        return (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">{t.optionalKickstart}</h2>
            {textInput(t.labels.strategicObjective, state.strategicObjective, (v) => setField("strategicObjective", v))}
            {textInput(t.labels.targetProcess, state.targetProcess, (v) => setField("targetProcess", v))}
            {textInput(t.labels.currentFriction, state.currentFriction, (v) => setField("currentFriction", v))}
            {textInput(t.labels.impactedDepartment, state.impactedDepartment, (v) => setField("impactedDepartment", v))}
            {textInput(t.labels.criticalConstraints, state.criticalConstraints, (v) => setField("criticalConstraints", v))}
            <button onClick={runKickstart} className="rounded-xl bg-black px-4 py-2 text-sm text-white">
              {t.actions.generateKickstart}
            </button>
            {kickstartNotice ? <p className="text-sm text-emerald-700">{kickstartNotice}</p> : null}
          </div>
        );
      case 1:
        return (
          <div className="space-y-4">
            {textInput(t.labels.title, state.title, (v) => setField("title", v), 2)}
            {textInput(t.labels.contextProcess, state.contextProcess, (v) => setField("contextProcess", v), 5)}
          </div>
        );
      case 2:
        return textInput(t.labels.problem, state.problem, (v) => setField("problem", v), 6);
      case 3:
        return textInput(t.labels.aiSolution, state.aiSolution, (v) => setField("aiSolution", v), 6);
      case 4:
        return textInput(t.labels.businessValue, state.businessValue, (v) => setField("businessValue", v), 6);
      case 5:
        return textInput(t.labels.dataReadiness, state.dataReadiness, (v) => setField("dataReadiness", v), 6);
      case 6:
        return textInput(t.labels.technicalReadiness, state.technicalReadiness, (v) => setField("technicalReadiness", v), 6);
      case 7:
        return textInput(t.labels.riskGovernance, state.riskGovernance, (v) => setField("riskGovernance", v), 6);
      case 8:
        return (
          <div className="space-y-4">
            {textInput(t.labels.reviewNotes, state.reviewNotes, (v) => setField("reviewNotes", v), 4)}
            <button onClick={generateAmoa} className="rounded-xl bg-indigo-600 px-4 py-2 text-sm text-white">
              {t.actions.generateAmoa}
            </button>
            {amoaDocument ? (
              <div className="space-y-2">
                <h3 className="font-medium">{t.amoaTitle}</h3>
                <pre className="max-h-80 overflow-auto rounded-xl border border-black/15 bg-white p-3 text-xs">
                  {amoaDocument}
                </pre>
                <button onClick={downloadAmoa} className="rounded-xl border border-black/20 px-4 py-2 text-sm">
                  {t.actions.download}
                </button>
              </div>
            ) : null}
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 p-6 md:p-10">
      <div className="mx-auto max-w-4xl space-y-6">
        <header className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-black/5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold">{t.appTitle}</h1>
              <p className="mt-1 text-sm text-slate-600">{t.appSubtitle}</p>
            </div>
            <div className="flex rounded-xl border border-black/10 bg-white p-1">
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
              <span>Progress</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 rounded-full bg-slate-200">
              <div className="h-2 rounded-full bg-indigo-600" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </header>

        <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-black/5">
          {step >= 1 && step <= 8 ? <h2 className="mb-4 text-lg font-semibold">{t.steps[step - 1]}</h2> : null}
          {wizardBody()}

          <div className="mt-6 flex flex-wrap items-center gap-2">
            <button
              onClick={() => setStep((s) => Math.max(0, s - 1))}
              className="rounded-xl border border-black/20 px-4 py-2 text-sm"
            >
              {t.actions.previous}
            </button>
            <button
              onClick={saveAndQuit}
              className="rounded-xl border border-black/20 px-4 py-2 text-sm"
            >
              {t.actions.saveQuit}
            </button>
            <button
              onClick={() => setStep((s) => Math.min(8, s + 1))}
              className="rounded-xl bg-black px-4 py-2 text-sm text-white"
            >
              {t.actions.next}
            </button>
          </div>
          {saveNotice ? <p className="mt-2 text-sm text-slate-600">{saveNotice}</p> : null}
        </section>
      </div>
    </main>
  );
}
