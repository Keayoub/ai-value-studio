"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  ApiClientError,
  BrowserApiClient,
} from "@/features/api/browser-api-client";
import type {
  ScoreDimension,
  ScorecardVersion,
  UseCase,
  UseCaseScorecards,
} from "@/features/api/types";
import { useAuth } from "@/features/auth/auth-context";
import { getPublicRuntimeConfig } from "@/features/auth/runtime";
import { LabeledField } from "@/features/studio/shared";
import type { Locale } from "@/features/studio/wizard/copy";

const runtimeConfig = getPublicRuntimeConfig(process.env);

type ScorecardCopy = {
  title: string;
  description: string;
  loadError: string;
  emptyTitle: string;
  emptyDescription: string;
  forbiddenTitle: string;
  forbiddenDescription: string;
  valueInputs: string;
  saveValue: string;
  recalculate: string;
  scenarioComparison: string;
  scenariosCaption: string;
  sensitivity: string;
  snapshot: string;
  scoreSummary: string;
  radar: string;
  gauge: string;
  history: string;
  historyCaption: string;
  override: string;
  overrideTitle: string;
  overrideDescription: string;
  dimension: string;
  score: string;
  reason: string;
  submitOverride: string;
  close: string;
  annualVolume: string;
  timeSavedHours: string;
  hourlyCost: string;
  errorReductionRate: string;
  averageErrorCost: string;
  revenueCapacityValue: string;
  estimatedAnnualCost: string;
  timeToImpactMonths: string;
  primaryKpi: string;
  kpiTarget: string;
  confidence: string;
  currency: string;
  priorityScore: string;
  category: string;
  readiness: string;
  riskProfile: string;
  overallConfidence: string;
  formula: string;
  sourceSnapshot: string;
  weights: string;
  netAnnualValue: string;
  npv3y: string;
  payback: string;
  notReached: string;
  baseline: string;
  conservative: string;
  optimistic: string;
  low: string;
  medium: string;
  high: string;
  current: string;
  dataTableDimension: string;
  dataTableWeight: string;
  dataTableScore: string;
  dataTableJustification: string;
  dataTableConfidence: string;
  dataTableSource: string;
  historyVersion: string;
  historyDate: string;
  historyOverride: string;
  historyRisk: string;
  sensitivityLever: Record<string, string>;
  dimensions: Record<ScoreDimension, string>;
  categories: Record<string, string>;
  risks: Record<string, string>;
  toasts: {
    valueSaved: string;
    scorecardRecalculated: string;
    overrideSaved: string;
  };
};

const scorecardCopy: Record<Locale, ScorecardCopy> = {
  fr: {
    title: "Scorecard de valeur et de priorité",
    description:
      "Les calculs restent déterministes et côté serveur. Le client affiche uniquement les résultats versionnés, la formule et les sources.",
    loadError: "Impossible de charger le scorecard.",
    emptyTitle: "Scorecard indisponible",
    emptyDescription:
      "Soumettez d’abord une évaluation courante pour initialiser la vue valeur/scoring.",
    forbiddenTitle: "Accès refusé",
    forbiddenDescription:
      "Vous pouvez consulter ce scorecard uniquement si vous êtes assigné au programme ou au cas d’usage.",
    valueInputs: "Entrées de valeur",
    saveValue: "Enregistrer la valeur",
    recalculate: "Recalculer le scorecard",
    scenarioComparison: "Comparaison des trois scénarios",
    scenariosCaption: "Résultats baseline, prudent et optimiste",
    sensitivity: "Sensibilité ±20%",
    snapshot: "Formule, sources et snapshot",
    scoreSummary: "Synthèse du score",
    radar: "Radar des six dimensions",
    gauge: "Jauge du priority score",
    history: "Historique des versions",
    historyCaption: "Historique immuable des versions de scorecard",
    override: "Surcharge consultant",
    overrideTitle: "Créer une nouvelle version avec surcharge",
    overrideDescription:
      "La surcharge manuelle reste immuable: elle crée toujours une nouvelle version de scorecard.",
    dimension: "Dimension",
    score: "Note",
    reason: "Raison de la surcharge",
    submitOverride: "Créer la nouvelle version",
    close: "Fermer",
    annualVolume: "Volume annualisé",
    timeSavedHours: "Temps gagné par transaction (heures)",
    hourlyCost: "Coût horaire moyen",
    errorReductionRate: "Réduction attendue du taux d’erreur (%)",
    averageErrorCost: "Coût moyen d’une erreur",
    revenueCapacityValue: "Impact annuel revenu/capacité",
    estimatedAnnualCost: "Coût annuel estimé",
    timeToImpactMonths: "Temps avant impact (mois)",
    primaryKpi: "KPI principal",
    kpiTarget: "Cible du KPI",
    confidence: "Confiance",
    currency: "Devise",
    priorityScore: "Priority score",
    category: "Catégorie",
    readiness: "Readiness moyenne",
    riskProfile: "Profil de risque",
    overallConfidence: "Confiance globale",
    formula: "Formule",
    sourceSnapshot: "Snapshot source",
    weights: "Poids actifs",
    netAnnualValue: "Valeur nette annuelle",
    npv3y: "NPV 3 ans",
    payback: "Payback",
    notReached: "Non atteint sous 36 mois",
    baseline: "Baseline",
    conservative: "Prudent",
    optimistic: "Optimiste",
    low: "Faible",
    medium: "Moyenne",
    high: "Élevée",
    current: "Courante",
    dataTableDimension: "Dimension",
    dataTableWeight: "Poids",
    dataTableScore: "Note",
    dataTableJustification: "Justification",
    dataTableConfidence: "Confiance",
    dataTableSource: "Source",
    historyVersion: "Version",
    historyDate: "Date",
    historyOverride: "Surcharge",
    historyRisk: "Risque",
    sensitivityLever: {
      time_saved_hours: "Temps gagné",
      error_reduction_rate: "Réduction d’erreur",
      revenue_capacity_value: "Revenu/capacité",
    },
    dimensions: {
      business_value: "Valeur business",
      current_friction: "Friction actuelle",
      data_feasibility: "Faisabilité data",
      technical_feasibility: "Faisabilité technique",
      adoption_potential: "Adoption",
      risk_governance: "Risque & gouvernance",
    },
    categories: {
      "Quick Win": "Quick Win",
      "Strategic Bet": "Strategic Bet",
      Foundation: "Foundation",
      Defer: "Defer",
      Reject: "Reject",
    },
    risks: {
      Low: "Faible",
      Medium: "Moyen",
      High: "Élevé",
      Critical: "Critique",
    },
    toasts: {
      valueSaved: "Valeur enregistrée",
      scorecardRecalculated: "Scorecard recalculé",
      overrideSaved: "Nouvelle version créée",
    },
  },
  en: {
    title: "Value and priority scorecard",
    description:
      "All calculations stay deterministic and server-side. The client renders only versioned results, formulas, and sources.",
    loadError: "Could not load the scorecard.",
    emptyTitle: "Scorecard unavailable",
    emptyDescription: "Submit a current assessment first to initialize value and scoring.",
    forbiddenTitle: "Access denied",
    forbiddenDescription: "You can view this scorecard only when assigned to the program or use case.",
    valueInputs: "Value inputs",
    saveValue: "Save value",
    recalculate: "Recalculate scorecard",
    scenarioComparison: "Three-scenario comparison",
    scenariosCaption: "Baseline, conservative, and optimistic outputs",
    sensitivity: "Sensitivity ±20%",
    snapshot: "Formula, sources, and snapshot",
    scoreSummary: "Score summary",
    radar: "Six-dimension radar",
    gauge: "Priority score gauge",
    history: "Version history",
    historyCaption: "Immutable scorecard version history",
    override: "Consultant override",
    overrideTitle: "Create a new overridden version",
    overrideDescription:
      "Manual overrides are immutable: they always create a new scorecard version.",
    dimension: "Dimension",
    score: "Score",
    reason: "Override reason",
    submitOverride: "Create new version",
    close: "Close",
    annualVolume: "Annualized volume",
    timeSavedHours: "Time saved per transaction (hours)",
    hourlyCost: "Average hourly cost",
    errorReductionRate: "Expected error reduction (%)",
    averageErrorCost: "Average error cost",
    revenueCapacityValue: "Annual revenue/capacity impact",
    estimatedAnnualCost: "Estimated annual cost",
    timeToImpactMonths: "Time to impact (months)",
    primaryKpi: "Primary KPI",
    kpiTarget: "KPI target",
    confidence: "Confidence",
    currency: "Currency",
    priorityScore: "Priority score",
    category: "Category",
    readiness: "Average readiness",
    riskProfile: "Risk profile",
    overallConfidence: "Overall confidence",
    formula: "Formula",
    sourceSnapshot: "Source snapshot",
    weights: "Active weights",
    netAnnualValue: "Net annual value",
    npv3y: "3-year NPV",
    payback: "Payback",
    notReached: "Not reached within 36 months",
    baseline: "Baseline",
    conservative: "Conservative",
    optimistic: "Optimistic",
    low: "Low",
    medium: "Medium",
    high: "High",
    current: "Current",
    dataTableDimension: "Dimension",
    dataTableWeight: "Weight",
    dataTableScore: "Score",
    dataTableJustification: "Justification",
    dataTableConfidence: "Confidence",
    dataTableSource: "Source",
    historyVersion: "Version",
    historyDate: "Date",
    historyOverride: "Override",
    historyRisk: "Risk",
    sensitivityLever: {
      time_saved_hours: "Time saved",
      error_reduction_rate: "Error reduction",
      revenue_capacity_value: "Revenue/capacity",
    },
    dimensions: {
      business_value: "Business value",
      current_friction: "Current friction",
      data_feasibility: "Data feasibility",
      technical_feasibility: "Technical feasibility",
      adoption_potential: "Adoption",
      risk_governance: "Risk & governance",
    },
    categories: {
      "Quick Win": "Quick Win",
      "Strategic Bet": "Strategic Bet",
      Foundation: "Foundation",
      Defer: "Defer",
      Reject: "Reject",
    },
    risks: {
      Low: "Low",
      Medium: "Medium",
      High: "High",
      Critical: "Critical",
    },
    toasts: {
      valueSaved: "Value saved",
      scorecardRecalculated: "Scorecard recalculated",
      overrideSaved: "New version created",
    },
  },
};

type ValueFormState = {
  annual_volume: string;
  time_saved_hours: string;
  hourly_cost: string;
  error_reduction_rate: string;
  average_error_cost: string;
  revenue_capacity_value: string;
  estimated_annual_cost: string;
  time_to_impact_months: string;
  primary_kpi: string;
  kpi_target: string;
  confidence: string;
  currency: string;
};

function problemMessage(error: unknown, fallback: string) {
  if (error instanceof ApiClientError) {
    return error.problem.detail;
  }
  return error instanceof Error ? error.message : fallback;
}

function formFromBundle(bundle: UseCaseScorecards): ValueFormState {
  return {
    annual_volume: String(bundle.value_assessment.annual_volume),
    time_saved_hours: String(bundle.value_assessment.time_saved_hours),
    hourly_cost: String(bundle.value_assessment.hourly_cost),
    error_reduction_rate: String(bundle.value_assessment.error_reduction_rate),
    average_error_cost: String(bundle.value_assessment.average_error_cost),
    revenue_capacity_value: String(bundle.value_assessment.revenue_capacity_value),
    estimated_annual_cost: String(bundle.value_assessment.estimated_annual_cost),
    time_to_impact_months: String(bundle.value_assessment.time_to_impact_months),
    primary_kpi: bundle.value_assessment.primary_kpi,
    kpi_target: bundle.value_assessment.kpi_target,
    confidence: bundle.value_assessment.confidence,
    currency: bundle.value_assessment.currency,
  };
}

export function UseCaseScorecard({
  workspaceId,
  programId,
  useCase,
  locale,
  onUseCaseSync,
}: {
  workspaceId: string;
  programId: string;
  useCase: UseCase;
  locale: Locale;
  onUseCaseSync?: (patch: Pick<UseCase, "priority_score" | "category" | "score_version" | "confidence_level">) => void;
}) {
  const auth = useAuth();
  const toast = useToast();
  const labels = scorecardCopy[locale];
  const api = useMemo(
    () => new BrowserApiClient(runtimeConfig.apiBaseUrl, auth.getAuthHeaders),
    [auth.getAuthHeaders],
  );
  const [bundle, setBundle] = useState<UseCaseScorecards | null>(null);
  const [form, setForm] = useState<ValueFormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [saving, setSaving] = useState(false);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideForm, setOverrideForm] = useState({
    dimension: "risk_governance" as ScoreDimension,
    score: "5",
    reason: "",
  });
  const onUseCaseSyncRef = useRef(onUseCaseSync);

  useEffect(() => {
    onUseCaseSyncRef.current = onUseCaseSync;
  }, [onUseCaseSync]);

  const applyBundle = useCallback(
    (nextBundle: UseCaseScorecards) => {
      setBundle(nextBundle);
      setForm(formFromBundle(nextBundle));
      setError(null);
      setForbidden(false);
      if (nextBundle.current_scorecard && onUseCaseSyncRef.current) {
        onUseCaseSyncRef.current({
          priority_score: nextBundle.current_scorecard.priority_score,
          category: nextBundle.current_scorecard.category,
          score_version: nextBundle.current_scorecard.version,
          confidence_level: nextBundle.current_scorecard.confidence_level,
        });
      }
    },
    [],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const nextBundle = await api.getUseCaseScorecards(workspaceId, programId, useCase.id);
      applyBundle(nextBundle);
    } catch (loadError) {
      if (loadError instanceof ApiClientError && loadError.problem.status === 403) {
        setForbidden(true);
      } else if (loadError instanceof ApiClientError && loadError.problem.status === 404) {
        setBundle(null);
      } else {
        setError(problemMessage(loadError, labels.loadError));
      }
    } finally {
      setLoading(false);
    }
  }, [api, applyBundle, labels.loadError, programId, useCase.id, workspaceId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const isReadOnly = bundle?.read_only ?? true;

  const saveValueAssessment = useCallback(async () => {
    if (!form) {
      return null;
    }
    setSaving(true);
    try {
      const nextBundle = await api.putValueAssessment(workspaceId, programId, useCase.id, {
        annual_volume: Number(form.annual_volume),
        time_saved_hours: Number(form.time_saved_hours),
        hourly_cost: Number(form.hourly_cost),
        error_reduction_rate: Number(form.error_reduction_rate),
        average_error_cost: Number(form.average_error_cost),
        revenue_capacity_value: Number(form.revenue_capacity_value),
        estimated_annual_cost: Number(form.estimated_annual_cost),
        time_to_impact_months: Number(form.time_to_impact_months),
        primary_kpi: form.primary_kpi,
        kpi_target: form.kpi_target,
        confidence: form.confidence,
        currency: form.currency,
      });
      applyBundle(nextBundle);
      toast.push({ tone: "success", title: labels.toasts.valueSaved, detail: useCase.title });
      return nextBundle;
    } catch (saveError) {
      toast.push({
        tone: "error",
        title: labels.loadError,
        detail: problemMessage(saveError, labels.loadError),
      });
      return null;
    } finally {
      setSaving(false);
    }
  }, [api, applyBundle, form, labels.loadError, labels.toasts.valueSaved, programId, toast, useCase.id, useCase.title, workspaceId]);

  const handleRecalculate = useCallback(async () => {
    const synced = await saveValueAssessment();
    if (!synced) {
      return;
    }
    setSaving(true);
    try {
      const nextBundle = await api.recalculateScorecards(workspaceId, programId, useCase.id);
      applyBundle(nextBundle);
      toast.push({
        tone: "success",
        title: labels.toasts.scorecardRecalculated,
        detail: useCase.title,
      });
    } catch (recalcError) {
      toast.push({
        tone: "error",
        title: labels.loadError,
        detail: problemMessage(recalcError, labels.loadError),
      });
    } finally {
      setSaving(false);
    }
  }, [api, applyBundle, labels.loadError, labels.toasts.scorecardRecalculated, programId, saveValueAssessment, toast, useCase.id, useCase.title, workspaceId]);

  const handleOverride = useCallback(async () => {
    setSaving(true);
    try {
      const nextBundle = await api.overrideScorecard(workspaceId, programId, useCase.id, {
        dimension: overrideForm.dimension,
        score: Number(overrideForm.score),
        reason: overrideForm.reason,
      });
      applyBundle(nextBundle);
      setOverrideOpen(false);
      setOverrideForm({ dimension: "risk_governance", score: "5", reason: "" });
      toast.push({
        tone: "success",
        title: labels.toasts.overrideSaved,
        detail: useCase.title,
      });
    } catch (overrideError) {
      toast.push({
        tone: "error",
        title: labels.loadError,
        detail: problemMessage(overrideError, labels.loadError),
      });
    } finally {
      setSaving(false);
    }
  }, [api, applyBundle, labels.loadError, labels.toasts.overrideSaved, overrideForm.dimension, overrideForm.reason, overrideForm.score, programId, toast, useCase.id, useCase.title, workspaceId]);

  if (loading) {
    return (
      <Card>
        <CardHeader title={labels.title} description={labels.description} />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-56 rounded-2xl" />
          <Skeleton className="h-56 rounded-2xl" />
        </div>
      </Card>
    );
  }

  if (forbidden) {
    return <EmptyState title={labels.forbiddenTitle} description={labels.forbiddenDescription} />;
  }

  if (error) {
    return <EmptyState title={labels.loadError} description={error} />;
  }

  if (!bundle || !form) {
    return <EmptyState title={labels.emptyTitle} description={labels.emptyDescription} />;
  }

  const current = bundle.current_scorecard;
  const scenarioRows = bundle.value_assessment.scenarios.map((scenario) => [
    labels[scenario.name as keyof Pick<ScorecardCopy, "baseline" | "conservative" | "optimistic">] ?? scenario.name,
    formatCurrency(scenario.net_annual_value, locale, bundle.value_assessment.currency),
    formatCurrency(scenario.npv_3y, locale, bundle.value_assessment.currency),
    scenario.payback_months === null ? labels.notReached : formatMonths(scenario.payback_months, locale),
  ]);

  return (
    <section className="space-y-6">
      <Card>
        <CardHeader title={labels.title} description={labels.description} />
        <div className="grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
          <div className="space-y-4">
            <h3 className="text-base font-semibold text-[var(--studio-foreground)]">
              {labels.valueInputs}
            </h3>
            <div className="grid gap-4 md:grid-cols-2">
              <NumberField label={labels.annualVolume} value={form.annual_volume} onChange={(value) => setForm((currentForm) => currentForm ? { ...currentForm, annual_volume: value } : currentForm)} disabled={isReadOnly || saving} />
              <NumberField label={labels.timeSavedHours} value={form.time_saved_hours} onChange={(value) => setForm((currentForm) => currentForm ? { ...currentForm, time_saved_hours: value } : currentForm)} disabled={isReadOnly || saving} />
              <NumberField label={labels.hourlyCost} value={form.hourly_cost} onChange={(value) => setForm((currentForm) => currentForm ? { ...currentForm, hourly_cost: value } : currentForm)} disabled={isReadOnly || saving} />
              <NumberField label={labels.errorReductionRate} value={form.error_reduction_rate} onChange={(value) => setForm((currentForm) => currentForm ? { ...currentForm, error_reduction_rate: value } : currentForm)} disabled={isReadOnly || saving} />
              <NumberField label={labels.averageErrorCost} value={form.average_error_cost} onChange={(value) => setForm((currentForm) => currentForm ? { ...currentForm, average_error_cost: value } : currentForm)} disabled={isReadOnly || saving} />
              <NumberField label={labels.revenueCapacityValue} value={form.revenue_capacity_value} onChange={(value) => setForm((currentForm) => currentForm ? { ...currentForm, revenue_capacity_value: value } : currentForm)} disabled={isReadOnly || saving} />
              <NumberField label={labels.estimatedAnnualCost} value={form.estimated_annual_cost} onChange={(value) => setForm((currentForm) => currentForm ? { ...currentForm, estimated_annual_cost: value } : currentForm)} disabled={isReadOnly || saving} />
              <NumberField label={labels.timeToImpactMonths} value={form.time_to_impact_months} onChange={(value) => setForm((currentForm) => currentForm ? { ...currentForm, time_to_impact_months: value } : currentForm)} disabled={isReadOnly || saving} />
              <LabeledField label={labels.primaryKpi}>
                <Input value={form.primary_kpi} onChange={(event) => setForm((currentForm) => currentForm ? { ...currentForm, primary_kpi: event.target.value } : currentForm)} disabled={isReadOnly || saving} />
              </LabeledField>
              <LabeledField label={labels.kpiTarget}>
                <Input value={form.kpi_target} onChange={(event) => setForm((currentForm) => currentForm ? { ...currentForm, kpi_target: event.target.value } : currentForm)} disabled={isReadOnly || saving} />
              </LabeledField>
              <LabeledField label={labels.confidence}>
                <Select value={form.confidence} onChange={(event) => setForm((currentForm) => currentForm ? { ...currentForm, confidence: event.target.value } : currentForm)} disabled={isReadOnly || saving}>
                  <option value="low">{labels.low}</option>
                  <option value="medium">{labels.medium}</option>
                  <option value="high">{labels.high}</option>
                </Select>
              </LabeledField>
              <LabeledField label={labels.currency}>
                <Input value={form.currency} onChange={(event) => setForm((currentForm) => currentForm ? { ...currentForm, currency: event.target.value.toUpperCase() } : currentForm)} maxLength={3} disabled={isReadOnly || saving} />
              </LabeledField>
            </div>
            <div className="flex flex-wrap gap-3">
              {!isReadOnly ? (
                <>
                  <Button onClick={() => void saveValueAssessment()} disabled={saving}>
                    {labels.saveValue}
                  </Button>
                  <Button variant="secondary" onClick={() => void handleRecalculate()} disabled={saving}>
                    {labels.recalculate}
                  </Button>
                </>
              ) : (
                <Badge tone="info">{labels.current}</Badge>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-base font-semibold text-[var(--studio-foreground)]">
              {labels.scoreSummary}
            </h3>
            {current ? (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  <MetricCard label={labels.priorityScore} value={current.priority_score.toFixed(3)} />
                  <MetricCard label={labels.category} value={labels.categories[current.category] ?? current.category} />
                  <MetricCard label={labels.readiness} value={current.readiness_average.toFixed(3)} />
                  <MetricCard label={labels.riskProfile} value={labels.risks[current.risk_profile] ?? current.risk_profile} />
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <GaugeChart
                    locale={locale}
                    value={current.priority_score}
                    title={labels.gauge}
                    subtitle={labels.overallConfidence}
                    confidence={current.confidence_level}
                  />
                  <RadarChart
                    dimensions={current.dimensions}
                    labels={labels.dimensions}
                    title={labels.radar}
                  />
                </div>
              </>
            ) : (
              <EmptyState title={labels.scoreSummary} description={labels.emptyDescription} />
            )}
          </div>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
        <Card>
          <CardHeader title={labels.scenarioComparison} description={labels.scenariosCaption} />
          <div className="grid gap-4 md:grid-cols-3">
            {bundle.value_assessment.scenarios.map((scenario) => (
              <article key={scenario.name} className="rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] p-4">
                <p className="text-sm font-semibold text-[var(--studio-brand)]">
                  {labels[scenario.name as keyof Pick<ScorecardCopy, "baseline" | "conservative" | "optimistic">] ?? scenario.name}
                </p>
                <dl className="mt-3 space-y-2 text-sm">
                  <MetricRow label={labels.netAnnualValue} value={formatCurrency(scenario.net_annual_value, locale, bundle.value_assessment.currency)} />
                  <MetricRow label={labels.npv3y} value={formatCurrency(scenario.npv_3y, locale, bundle.value_assessment.currency)} />
                  <MetricRow
                    label={labels.payback}
                    value={scenario.payback_months === null ? labels.notReached : formatMonths(scenario.payback_months, locale)}
                  />
                </dl>
              </article>
            ))}
          </div>
          <div className="mt-4">
            <DataTable
              caption={labels.scenariosCaption}
              headers={[labels.scenarioComparison, labels.netAnnualValue, labels.npv3y, labels.payback]}
              rows={scenarioRows}
              empty={<p className="text-sm text-[var(--studio-muted)]">{labels.emptyDescription}</p>}
            />
          </div>
        </Card>

        <Card>
          <CardHeader title={labels.sensitivity} />
          <TornadoChart
            sensitivities={bundle.value_assessment.sensitivities}
            currency={bundle.value_assessment.currency}
            locale={locale}
            leverLabels={labels.sensitivityLever}
          />
        </Card>
      </div>

      {current ? (
        <Card>
          <CardHeader
            title={labels.snapshot}
            action={
              bundle.can_override && !bundle.read_only ? (
                <Button variant="secondary" onClick={() => setOverrideOpen(true)}>
                  {labels.override}
                </Button>
              ) : null
            }
          />
          <div className="grid gap-6 xl:grid-cols-[1fr,1fr]">
            <div className="space-y-4">
              <div className="rounded-2xl border border-[var(--studio-border)] p-4">
                <h3 className="font-semibold text-[var(--studio-foreground)]">{labels.formula}</h3>
                <p className="mt-2 text-sm text-[var(--studio-muted)]">
                  {String(current.formula_snapshot.priority_formula)} · {String(current.formula_snapshot.readiness_formula)}
                </p>
                <p className="mt-2 text-sm text-[var(--studio-muted)]">
                  {labels.weights}: {Object.entries(bundle.score_configuration.weights)
                    .map(([key, value]) => `${labels.dimensions[key as ScoreDimension]} ${Math.round(value * 100)}%`)
                    .join(" · ")}
                </p>
              </div>
              <div className="rounded-2xl border border-[var(--studio-border)] p-4">
                <h3 className="font-semibold text-[var(--studio-foreground)]">{labels.sourceSnapshot}</h3>
                <dl className="mt-3 grid gap-2 text-sm md:grid-cols-2">
                  {Object.entries(bundle.value_assessment.source_snapshot.question_sources ?? {}).map(([key, value]) => (
                    <div key={key}>
                      <dt className="font-medium text-[var(--studio-muted)]">{key}</dt>
                      <dd className="text-[var(--studio-foreground)]">{formatJsonValue(value)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>
            <div className="space-y-4">
              <DataTable
                caption={labels.radar}
                headers={[
                  labels.dataTableDimension,
                  labels.dataTableWeight,
                  labels.dataTableScore,
                  labels.dataTableConfidence,
                  labels.dataTableSource,
                  labels.dataTableJustification,
                ]}
                rows={current.dimensions.map((dimension) => [
                  labels.dimensions[dimension.dimension],
                  `${Math.round(dimension.weight * 100)}%`,
                  dimension.score,
                  titleCase(dimension.confidence),
                  dimension.source,
                  <span key={`${dimension.id}-justification`} className="block max-w-lg">
                    {dimension.justification}
                    {dimension.override_reason ? ` (${dimension.override_reason})` : ""}
                  </span>,
                ])}
                empty={<p className="text-sm text-[var(--studio-muted)]">{labels.emptyDescription}</p>}
              />
            </div>
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader title={labels.history} />
        <DataTable
          caption={labels.historyCaption}
          headers={[
            labels.historyVersion,
            labels.historyDate,
            labels.priorityScore,
            labels.category,
            labels.historyRisk,
            labels.historyOverride,
          ]}
          rows={bundle.history.map((entry) => [
            entry.version,
            formatDate(entry.created_at, locale),
            entry.priority_score.toFixed(3),
            labels.categories[entry.category] ?? entry.category,
            labels.risks[entry.risk_profile] ?? entry.risk_profile,
            entry.manual_override ? (entry.override_reason ?? labels.override) : "—",
          ])}
          empty={<p className="text-sm text-[var(--studio-muted)]">{labels.emptyDescription}</p>}
        />
      </Card>

      <Dialog
        open={overrideOpen}
        title={labels.overrideTitle}
        description={labels.overrideDescription}
        onClose={() => setOverrideOpen(false)}
      >
        <div className="space-y-4">
          <LabeledField label={labels.dimension}>
            <Select
              value={overrideForm.dimension}
              onChange={(event) =>
                setOverrideForm((currentForm) => ({
                  ...currentForm,
                  dimension: event.target.value as ScoreDimension,
                }))
              }
            >
              {Object.entries(labels.dimensions).map(([key, value]) => (
                <option key={key} value={key}>
                  {value}
                </option>
              ))}
            </Select>
          </LabeledField>
          <LabeledField label={labels.score}>
            <Select
              value={overrideForm.score}
              onChange={(event) =>
                setOverrideForm((currentForm) => ({ ...currentForm, score: event.target.value }))
              }
            >
              {[1, 2, 3, 4, 5].map((score) => (
                <option key={score} value={score}>
                  {score}
                </option>
              ))}
            </Select>
          </LabeledField>
          <LabeledField label={labels.reason}>
            <Textarea
              value={overrideForm.reason}
              onChange={(event) =>
                setOverrideForm((currentForm) => ({ ...currentForm, reason: event.target.value }))
              }
            />
          </LabeledField>
          <div className="flex justify-end">
            <Button onClick={() => void handleOverride()} disabled={saving || !overrideForm.reason.trim()}>
              {labels.submitOverride}
            </Button>
          </div>
        </div>
      </Dialog>
    </section>
  );
}

function NumberField({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  return (
    <LabeledField label={label}>
      <Input value={value} inputMode="decimal" onChange={(event) => onChange(event.target.value)} disabled={disabled} />
    </LabeledField>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] p-4">
      <p className="text-sm font-medium text-[var(--studio-muted)]">{label}</p>
      <p className="mt-2 text-xl font-semibold text-[var(--studio-foreground)]">{value}</p>
    </div>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-[var(--studio-muted)]">{label}</dt>
      <dd className="text-right text-[var(--studio-foreground)]">{value}</dd>
    </div>
  );
}

function GaugeChart({
  title,
  subtitle,
  value,
  confidence,
  locale,
}: {
  title: string;
  subtitle: string;
  value: number;
  confidence: string;
  locale: Locale;
}) {
  const angle = -120 + ((Math.max(1, Math.min(5, value)) - 1) / 4) * 240;
  const radians = (angle * Math.PI) / 180;
  const x2 = 110 + Math.cos(radians) * 56;
  const y2 = 110 + Math.sin(radians) * 56;
  return (
    <figure className="rounded-2xl border border-[var(--studio-border)] p-4">
      <figcaption className="mb-3 text-sm font-semibold text-[var(--studio-foreground)]">
        {title}
      </figcaption>
      <svg viewBox="0 0 220 140" role="img" aria-label={`${title}: ${value.toFixed(3)}`}>
        <path d="M30 110 A80 80 0 0 1 190 110" fill="none" stroke="var(--studio-border)" strokeWidth="18" />
        <path d="M30 110 A80 80 0 0 1 110 30" fill="none" stroke="#d97706" strokeWidth="18" />
        <path d="M110 30 A80 80 0 0 1 190 110" fill="none" stroke="#1d4ed8" strokeWidth="18" />
        <line x1="110" y1="110" x2={x2} y2={y2} stroke="var(--studio-brand)" strokeWidth="4" strokeLinecap="round" />
        <circle cx="110" cy="110" r="6" fill="var(--studio-brand)" />
        <text x="110" y="102" textAnchor="middle" className="fill-[var(--studio-foreground)] text-[20px] font-semibold">
          {value.toFixed(3)}
        </text>
        <text x="110" y="126" textAnchor="middle" className="fill-[var(--studio-muted)] text-[11px]">
          {subtitle}: {titleCase(confidence)}
        </text>
      </svg>
      <p className="mt-2 text-sm text-[var(--studio-muted)]">
        {locale === "fr" ? "Échelle 1 à 5" : "Scale 1 to 5"}
      </p>
    </figure>
  );
}

function RadarChart({
  dimensions,
  labels,
  title,
}: {
  dimensions: ScorecardVersion["dimensions"];
  labels: Record<ScoreDimension, string>;
  title: string;
}) {
  const orderedDimensions: ScoreDimension[] = [
    "business_value",
    "current_friction",
    "data_feasibility",
    "technical_feasibility",
    "adoption_potential",
    "risk_governance",
  ];
  const points = orderedDimensions
    .map((dimension, index) => {
      const score = dimensions.find((entry) => entry.dimension === dimension)?.score ?? 0;
      const angle = (-90 + index * 60) * (Math.PI / 180);
      const radius = 70 * (score / 5);
      const x = 90 + Math.cos(angle) * radius;
      const y = 90 + Math.sin(angle) * radius;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <figure className="rounded-2xl border border-[var(--studio-border)] p-4">
      <figcaption className="mb-3 text-sm font-semibold text-[var(--studio-foreground)]">
        {title}
      </figcaption>
      <svg viewBox="0 0 220 220" role="img" aria-label={title}>
        {[14, 28, 42, 56, 70].map((radius) => (
          <circle key={radius} cx="90" cy="90" r={radius} fill="none" stroke="var(--studio-border)" strokeDasharray="4 4" />
        ))}
        {orderedDimensions.map((dimension, index) => {
          const angle = (-90 + index * 60) * (Math.PI / 180);
          const x = 90 + Math.cos(angle) * 78;
          const y = 90 + Math.sin(angle) * 78;
          return (
            <g key={dimension}>
              <line x1="90" y1="90" x2={x} y2={y} stroke="var(--studio-border)" />
              <text x={90 + Math.cos(angle) * 92} y={90 + Math.sin(angle) * 92} textAnchor="middle" className="fill-[var(--studio-muted)] text-[10px]">
                {labels[dimension]}
              </text>
            </g>
          );
        })}
        <polygon points={points} fill="rgb(30 64 175 / 0.18)" stroke="var(--studio-brand)" strokeWidth="2" />
      </svg>
    </figure>
  );
}

function TornadoChart({
  sensitivities,
  locale,
  currency,
  leverLabels,
}: {
  sensitivities: UseCaseScorecards["value_assessment"]["sensitivities"];
  locale: Locale;
  currency: string;
  leverLabels: Record<string, string>;
}) {
  const maxDelta = Math.max(
    1,
    ...sensitivities.flatMap((entry) => [Math.abs(entry.low_delta), Math.abs(entry.high_delta)]),
  );
  return (
    <div className="space-y-4">
      <svg viewBox="0 0 540 220" role="img" aria-label="Sensitivity tornado chart">
        <line x1="270" y1="10" x2="270" y2="200" stroke="var(--studio-border)" strokeDasharray="4 4" />
        {sensitivities.map((entry, index) => {
          const y = 36 + index * 56;
          const lowWidth = (Math.abs(entry.low_delta) / maxDelta) * 180;
          const highWidth = (Math.abs(entry.high_delta) / maxDelta) * 180;
          return (
            <g key={entry.lever}>
              <text x="10" y={y + 5} className="fill-[var(--studio-foreground)] text-[12px]">
                {leverLabels[entry.lever] ?? entry.lever}
              </text>
              <rect x={270 - lowWidth} y={y - 12} width={lowWidth} height="20" fill="#ef4444" rx="4" />
              <rect x={270} y={y - 12} width={highWidth} height="20" fill="#2563eb" rx="4" />
              <text x={270 - lowWidth - 8} y={y + 2} textAnchor="end" className="fill-[var(--studio-muted)] text-[10px]">
                {formatCurrency(entry.low_delta, locale, currency)}
              </text>
              <text x={270 + highWidth + 8} y={y + 2} className="fill-[var(--studio-muted)] text-[10px]">
                {formatCurrency(entry.high_delta, locale, currency)}
              </text>
            </g>
          );
        })}
      </svg>
      <dl className="space-y-3 text-sm">
        {sensitivities.map((entry) => (
          <div key={entry.lever} className="rounded-2xl bg-[var(--studio-surface-subtle)] p-3">
            <dt className="font-semibold text-[var(--studio-foreground)]">
              {leverLabels[entry.lever] ?? entry.lever}
            </dt>
            <dd className="mt-1 text-[var(--studio-muted)]">
              {formatCurrency(entry.low_delta, locale, currency)} / {formatCurrency(entry.high_delta, locale, currency)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function formatCurrency(value: number, locale: Locale, currency: string) {
  return new Intl.NumberFormat(locale === "fr" ? "fr-FR" : "en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatMonths(value: number, locale: Locale) {
  const formatted = new Intl.NumberFormat(locale === "fr" ? "fr-FR" : "en-US", {
    maximumFractionDigits: 2,
  }).format(value);
  return locale === "fr" ? `${formatted} mois` : `${formatted} months`;
}

function formatDate(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "fr" ? "fr-FR" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function titleCase(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatJsonValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value ?? "");
}
