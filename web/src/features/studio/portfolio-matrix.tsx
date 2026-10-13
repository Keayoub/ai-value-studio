"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import {
  ApiClientError,
  BrowserApiClient,
} from "@/features/api/browser-api-client";
import type {
  PortfolioItem,
  PortfolioResponse,
  Program,
  UseCaseStatus,
} from "@/features/api/types";
import { useAuth } from "@/features/auth/auth-context";
import { getPublicRuntimeConfig } from "@/features/auth/runtime";
import { formatUseCaseStatusLabel } from "@/features/studio/copy";
import { LabeledField } from "@/features/studio/shared";
import type { Locale } from "@/features/studio/wizard/copy";

const runtimeConfig = getPublicRuntimeConfig(process.env);

type PortfolioCopy = {
  title: string;
  description: string;
  filtersTitle: string;
  filtersDescription: string;
  program: string;
  status: string;
  department: string;
  risk: string;
  allPrograms: string;
  allStatuses: string;
  allDepartments: string;
  allRisks: string;
  clearFilters: string;
  retry: string;
  loading: string;
  errorTitle: string;
  emptyTitle: string;
  emptyDescription: string;
  filteredEmptyTitle: string;
  filteredEmptyDescription: string;
  toggleMatrix: string;
  toggleTable: string;
  matrixTitle: string;
  matrixDescription: string;
  tableTitle: string;
  tableDescription: string;
  detailsTitle: string;
  detailsDescription: string;
  explanationTitle: string;
  explanationDescription: string;
  businessValueAxis: string;
  readinessAxis: string;
  legendTitle: string;
  legendRisk: string;
  legendEffort: string;
  totalItems: string;
  categoryBreakdown: string;
  businessValueScore: string;
  readinessAverage: string;
  priorityScore: string;
  category: string;
  riskProfile: string;
  netAnnualValue: string;
  departmentLabel: string;
  statusLabel: string;
  confidenceLabel: string;
  effortLabel: string;
  updatedAt: string;
  noSelection: string;
  openUseCase: string;
  explanationHint: string;
  sortLabel: string;
  sortOptions: Record<PortfolioSort, string>;
  tableHeaders: string[];
  matrixAriaLabel: string;
  bubbleHint: string;
  matrixXLabel: string;
  matrixYLabel: string;
  riskLabels: Record<string, string>;
  riskLegendDescriptions: Record<string, string>;
  categories: Record<string, string>;
  noneVisible: string;
  toasts: {
    loadError: string;
  };
};

type PortfolioSort = "business-desc" | "readiness-desc" | "value-desc" | "updated-desc";
type PortfolioView = "matrix" | "table";

const portfolioCopy: Record<Locale, PortfolioCopy> = {
  fr: {
    title: "Matrice portefeuille IA",
    description:
      "Les positions proviennent des snapshots serveur: X = moyenne data/technique/adoption, Y = valeur métier, taille = effort, risque = couleur et motif.",
    filtersTitle: "Filtres portefeuille",
    filtersDescription: "Les filtres sont appliqués côté serveur pour respecter le périmètre autorisé.",
    program: "Programme",
    status: "Statut",
    department: "Département",
    risk: "Risque",
    allPrograms: "Tous les programmes visibles",
    allStatuses: "Tous les statuts",
    allDepartments: "Tous les départements",
    allRisks: "Tous les risques",
    clearFilters: "Réinitialiser",
    retry: "Réessayer",
    loading: "Chargement du portefeuille…",
    errorTitle: "Impossible de charger le portefeuille",
    emptyTitle: "Aucun cas d’usage scoré",
    emptyDescription:
      "Calculez au moins un scorecard courant pour alimenter ce portefeuille.",
    filteredEmptyTitle: "Aucun résultat pour ces filtres",
    filteredEmptyDescription:
      "Aucun cas d’usage scoré visible ne correspond aux filtres actuels. Ajustez-les ou réinitialisez-les sans quitter la page.",
    toggleMatrix: "Vue matrice",
    toggleTable: "Vue tableau",
    matrixTitle: "Positionnement portefeuille",
    matrixDescription:
      "Chaque point est navigable au clavier. Activez-le pour lire le détail complet.",
    tableTitle: "Alternative textuelle",
    tableDescription:
      "Le tableau reprend les mêmes positions et permet un tri rapide pour les revues de portefeuille.",
    detailsTitle: "Détail du cas d’usage",
    detailsDescription:
      "Le panneau de détail conserve une explication lisible du point sélectionné.",
    explanationTitle: "Lecture de la catégorie",
    explanationDescription:
      "La catégorie affichée reprend la classification déterministe versionnée côté serveur.",
    businessValueAxis: "Valeur métier (Y)",
    readinessAxis: "Readiness moyenne (X)",
    legendTitle: "Légende",
    legendRisk: "Risque",
    legendEffort: "Effort",
    totalItems: "Cas visibles",
    categoryBreakdown: "Répartition catégories",
    businessValueScore: "Valeur métier",
    readinessAverage: "Readiness",
    priorityScore: "Score de priorité",
    category: "Catégorie",
    riskProfile: "Risque",
    netAnnualValue: "Valeur nette annuelle",
    departmentLabel: "Département",
    statusLabel: "Statut",
    confidenceLabel: "Confiance",
    effortLabel: "Effort",
    updatedAt: "Mis à jour",
    noSelection: "Sélectionnez un point ou une ligne pour afficher le détail.",
    openUseCase: "Ouvrir le cas d’usage",
    explanationHint:
      "La bulle affiche la valeur nette dans l’infobulle native et le détail complet dans le panneau latéral.",
    sortLabel: "Tri du tableau",
    sortOptions: {
      "business-desc": "Valeur métier décroissante",
      "readiness-desc": "Readiness décroissante",
      "value-desc": "Valeur nette décroissante",
      "updated-desc": "Mise à jour récente",
    },
    tableHeaders: [
      "Cas d’usage",
      "Programme",
      "X — readiness",
      "Y — valeur métier",
      "Effort",
      "Catégorie",
      "Risque",
      "Valeur nette",
      "Accès",
    ],
    matrixAriaLabel: "Matrice portefeuille des cas d’usage scorés",
    bubbleHint: "La taille de la bulle représente l’effort estimé.",
    matrixXLabel: "X — readiness",
    matrixYLabel: "Y — valeur métier",
    riskLabels: {
      Low: "Faible",
      Medium: "Modéré",
      High: "Élevé",
      Critical: "Critique",
    },
    riskLegendDescriptions: {
      Low: "cercle plein",
      Medium: "carré pointé",
      High: "losange hachuré",
      Critical: "triangle croisé",
    },
    categories: {
      "Quick Win": "Quick win",
      "Strategic Bet": "Pari stratégique",
      Foundation: "Fondation",
      Defer: "À différer",
      Reject: "À rejeter",
    },
    noneVisible: "Aucune",
    toasts: {
      loadError: "Chargement impossible",
    },
  },
  en: {
    title: "AI portfolio matrix",
    description:
      "All positions come from server snapshots: X = mean data/technical/adoption, Y = business value, size = effort, risk = color and pattern.",
    filtersTitle: "Portfolio filters",
    filtersDescription: "Filters run server-side to preserve the authorized scope.",
    program: "Program",
    status: "Status",
    department: "Department",
    risk: "Risk",
    allPrograms: "All visible programs",
    allStatuses: "All statuses",
    allDepartments: "All departments",
    allRisks: "All risks",
    clearFilters: "Reset",
    retry: "Retry",
    loading: "Loading portfolio…",
    errorTitle: "Could not load the portfolio",
    emptyTitle: "No scored use case",
    emptyDescription: "Compute at least one current scorecard to populate the portfolio.",
    filteredEmptyTitle: "No result for these filters",
    filteredEmptyDescription:
      "No visible scored use case matches the current filters. Adjust or reset them without leaving the page.",
    toggleMatrix: "Matrix view",
    toggleTable: "Table view",
    matrixTitle: "Portfolio positioning",
    matrixDescription: "Each point is keyboard reachable. Activate one to inspect the full detail.",
    tableTitle: "Text alternative",
    tableDescription: "The table mirrors the matrix and supports quick portfolio sorting.",
    detailsTitle: "Use case detail",
    detailsDescription: "The detail panel keeps a readable explanation for the selected point.",
    explanationTitle: "Category reading",
    explanationDescription: "The category shown is the server-versioned deterministic classification.",
    businessValueAxis: "Business value (Y)",
    readinessAxis: "Average readiness (X)",
    legendTitle: "Legend",
    legendRisk: "Risk",
    legendEffort: "Effort",
    totalItems: "Visible cases",
    categoryBreakdown: "Category split",
    businessValueScore: "Business value",
    readinessAverage: "Readiness",
    priorityScore: "Priority score",
    category: "Category",
    riskProfile: "Risk",
    netAnnualValue: "Net annual value",
    departmentLabel: "Department",
    statusLabel: "Status",
    confidenceLabel: "Confidence",
    effortLabel: "Effort",
    updatedAt: "Updated",
    noSelection: "Select a point or a row to inspect the detail.",
    openUseCase: "Open use case",
    explanationHint: "The bubble exposes net value in the native tooltip and the full detail in the side panel.",
    sortLabel: "Table sort",
    sortOptions: {
      "business-desc": "Business value descending",
      "readiness-desc": "Readiness descending",
      "value-desc": "Net value descending",
      "updated-desc": "Recently updated",
    },
    tableHeaders: [
      "Use case",
      "Program",
      "X — readiness",
      "Y — business value",
      "Effort",
      "Category",
      "Risk",
      "Net value",
      "Access",
    ],
    matrixAriaLabel: "Portfolio matrix of scored use cases",
    bubbleHint: "Bubble size represents estimated effort.",
    matrixXLabel: "X — readiness",
    matrixYLabel: "Y — business value",
    riskLabels: {
      Low: "Low",
      Medium: "Medium",
      High: "High",
      Critical: "Critical",
    },
    riskLegendDescriptions: {
      Low: "solid circle",
      Medium: "dotted square",
      High: "hatched diamond",
      Critical: "crosshatched triangle",
    },
    categories: {
      "Quick Win": "Quick Win",
      "Strategic Bet": "Strategic Bet",
      Foundation: "Foundation",
      Defer: "Defer",
      Reject: "Reject",
    },
    noneVisible: "None",
    toasts: {
      loadError: "Unable to load",
    },
  },
};

function problemMessage(error: unknown, fallback: string) {
  if (error instanceof ApiClientError) {
    return error.problem.detail;
  }
  return error instanceof Error ? error.message : fallback;
}

export function PortfolioMatrix({
  workspaceId,
  visiblePrograms,
  locale,
}: {
  workspaceId: string;
  visiblePrograms: Program[];
  locale: Locale;
}) {
  const auth = useAuth();
  const toast = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const copy = portfolioCopy[locale];
  const api = useMemo(
    () => new BrowserApiClient(runtimeConfig.apiBaseUrl, auth.getAuthHeaders),
    [auth.getAuthHeaders],
  );
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedUseCaseId, setSelectedUseCaseId] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const view: PortfolioView =
    searchParams.get("portfolioView") === "table" ? "table" : "matrix";
  const sort = normalizeSort(searchParams.get("portfolioSort"));

  const filters = useMemo(
    () => ({
      programId: searchParams.get("programId"),
      status: searchParams.get("status"),
      department: searchParams.get("department"),
      risk: searchParams.get("risk"),
    }),
    [searchParams],
  );

  const updateQuery = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(patch)) {
        if (value) {
          next.set(key, value);
        } else {
          next.delete(key);
        }
      }
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname);
    },
    [pathname, router, searchParams],
  );

  const resetFilters = useCallback(() => {
    updateQuery({
      programId: null,
      status: null,
      department: null,
      risk: null,
    });
  }, [updateQuery]);

  const retryLoad = useCallback(() => {
    setReloadToken((current) => current + 1);
  }, []);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const nextPortfolio = await api.getPortfolio(workspaceId, filters);
        if (!active) {
          return;
        }
        setPortfolio(nextPortfolio);
        setSelectedUseCaseId((current) => {
          if (current && nextPortfolio.items.some((item) => item.use_case_id === current)) {
            return current;
          }
          return nextPortfolio.items[0]?.use_case_id ?? null;
        });
      } catch (loadError) {
        if (!active) {
          return;
        }
        const detail = problemMessage(loadError, copy.errorTitle);
        setError(detail);
        toast.push({
          tone: "error",
          title: copy.toasts.loadError,
          detail,
        });
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [api, copy.errorTitle, copy.toasts.loadError, filters, reloadToken, toast, workspaceId]);

  const sortedItems = useMemo(
    () => sortPortfolioItems(portfolio?.items ?? [], sort),
    [portfolio?.items, sort],
  );
  const selectedItem =
    sortedItems.find((item) => item.use_case_id === selectedUseCaseId) ?? sortedItems[0] ?? null;
  const availablePrograms = useMemo(() => {
    const visibleIds = new Set(visiblePrograms.map((program) => program.id));
    return (portfolio?.available_filters.programs ?? []).filter((program) => visibleIds.has(program.id));
  }, [portfolio?.available_filters.programs, visiblePrograms]);
  const hasActiveFilters = Boolean(
    filters.programId || filters.status || filters.department || filters.risk,
  );
  const hasVisibleScoredItems = Boolean(
    portfolio &&
      (
        portfolio.available_filters.programs.length ||
        portfolio.available_filters.statuses.length ||
        portfolio.available_filters.departments.length ||
        portfolio.available_filters.risks.length
      ),
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader title={copy.title} description={copy.description} />
          <div className="grid gap-4 md:grid-cols-4">
            <Skeleton className="h-20 rounded-2xl" />
            <Skeleton className="h-20 rounded-2xl" />
            <Skeleton className="h-20 rounded-2xl" />
            <Skeleton className="h-20 rounded-2xl" />
          </div>
        </Card>
        <div className="grid gap-6 xl:grid-cols-[1.25fr,0.75fr]">
          <Card>
            <Skeleton className="h-[420px] rounded-2xl" />
          </Card>
          <Card>
            <Skeleton className="h-[420px] rounded-2xl" />
          </Card>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState
        title={copy.errorTitle}
        description={error}
        actionLabel={copy.retry}
        onAction={retryLoad}
      />
    );
  }

  if (!portfolio) {
    return null;
  }

  const categoryBreakdownValue =
    Object.entries(portfolio.summary.category_counts)
      .map(([category, count]) => `${copy.categories[category] ?? category}: ${count}`)
      .join(" · ") || copy.noneVisible;
  const emptyStateTitle = hasActiveFilters ? copy.filteredEmptyTitle : copy.emptyTitle;
  const emptyStateDescription = hasActiveFilters
    ? copy.filteredEmptyDescription
    : copy.emptyDescription;

  return (
    <section className="space-y-6">
      <Card>
        <CardHeader title={copy.title} description={copy.description} />
        <div className="grid gap-4 xl:grid-cols-[1.25fr,0.75fr]">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <SummaryMetric label={copy.totalItems} value={String(portfolio.summary.total_items)} />
            <SummaryMetric label={copy.categoryBreakdown} value={categoryBreakdownValue} />
            <SummaryMetric
              label={copy.legendRisk}
              value={Object.values(copy.riskLabels).join(" · ")}
            />
            <SummaryMetric label={copy.legendEffort} value={copy.bubbleHint} />
          </div>
          <div className="rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] p-4">
            <p className="text-sm font-semibold text-[var(--studio-foreground)]">{copy.filtersTitle}</p>
            <p className="mt-1 text-sm text-[var(--studio-muted)]">{copy.filtersDescription}</p>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <LabeledField label={copy.program}>
                <Select
                  value={filters.programId ?? ""}
                  onChange={(event) => updateQuery({ programId: event.target.value || null })}
                >
                  <option value="">{copy.allPrograms}</option>
                  {availablePrograms.map((program) => (
                    <option key={program.id} value={program.id}>
                      {program.name} ({program.count})
                    </option>
                  ))}
                </Select>
              </LabeledField>
              <LabeledField label={copy.status}>
                <Select
                  value={filters.status ?? ""}
                  onChange={(event) => updateQuery({ status: event.target.value || null })}
                >
                  <option value="">{copy.allStatuses}</option>
                  {portfolio.available_filters.statuses.map((option) => (
                    <option key={option.value} value={option.value}>
                      {formatUseCaseStatusLabel(locale, option.value as UseCaseStatus)} ({option.count})
                    </option>
                  ))}
                </Select>
              </LabeledField>
              <LabeledField label={copy.department}>
                <Select
                  value={filters.department ?? ""}
                  onChange={(event) => updateQuery({ department: event.target.value || null })}
                >
                  <option value="">{copy.allDepartments}</option>
                  {portfolio.available_filters.departments.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label} ({option.count})
                    </option>
                  ))}
                </Select>
              </LabeledField>
              <LabeledField label={copy.risk}>
                <Select
                  value={filters.risk ?? ""}
                  onChange={(event) => updateQuery({ risk: event.target.value || null })}
                >
                  <option value="">{copy.allRisks}</option>
                  {portfolio.available_filters.risks.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label} ({option.count})
                    </option>
                  ))}
                </Select>
              </LabeledField>
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <Button
                variant="secondary"
                onClick={resetFilters}
              >
                {copy.clearFilters}
              </Button>
              <Button
                variant={view === "matrix" ? "primary" : "secondary"}
                onClick={() => updateQuery({ portfolioView: "matrix" })}
              >
                {copy.toggleMatrix}
              </Button>
              <Button
                variant={view === "table" ? "primary" : "secondary"}
                onClick={() => updateQuery({ portfolioView: "table" })}
              >
                {copy.toggleTable}
              </Button>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.25fr,0.75fr]">
        <Card>
          <CardHeader
            title={view === "matrix" ? copy.matrixTitle : copy.tableTitle}
            description={view === "matrix" ? copy.matrixDescription : copy.tableDescription}
          />
          <div className="flex flex-wrap items-end justify-between gap-4">
            <p className="text-sm text-[var(--studio-muted)]">{copy.explanationHint}</p>
            <LabeledField label={copy.sortLabel}>
              <Select
                value={sort}
                onChange={(event) => {
                  const nextSort = normalizeSort(event.target.value);
                  updateQuery({ portfolioSort: nextSort });
                }}
              >
                {Object.entries(copy.sortOptions).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </LabeledField>
          </div>
          {sortedItems.length === 0 ? (
            <EmptyState
              title={emptyStateTitle}
              description={emptyStateDescription}
              actionLabel={hasActiveFilters ? copy.clearFilters : undefined}
              onAction={hasActiveFilters ? resetFilters : undefined}
            />
          ) : view === "matrix" ? (
            <PortfolioSvgMatrix
              items={sortedItems}
              selectedUseCaseId={selectedItem?.use_case_id ?? null}
              locale={locale}
              copy={copy}
              onSelect={setSelectedUseCaseId}
            />
          ) : (
            <DataTable
              caption={copy.tableDescription}
              headers={copy.tableHeaders}
              rows={sortedItems.map((item) => [
                <button
                  key={`${item.use_case_id}-row`}
                  type="button"
                  className="text-left font-medium text-[var(--studio-accent)] underline underline-offset-2"
                  onClick={() => setSelectedUseCaseId(item.use_case_id)}
                >
                  {item.use_case_title}
                </button>,
                item.program_name,
                item.readiness_average.toFixed(2),
                String(item.business_value_score),
                item.effort_label_fr ?? "—",
                copy.categories[item.category] ?? item.category,
                copy.riskLabels[item.risk_profile] ?? item.risk_profile,
                formatCurrency(item.net_annual_value, locale, item.currency),
                <Link
                  key={`${item.use_case_id}-link`}
                  href={portfolioUseCaseHref(item)}
                  className="text-[var(--studio-accent)] underline underline-offset-2 hover:text-[var(--studio-accent-hover)]"
                >
                  {copy.openUseCase}
                </Link>,
              ])}
              empty={<p className="text-sm text-[var(--studio-muted)]">{emptyStateDescription}</p>}
            />
          )}
        </Card>

        <Card>
          <CardHeader title={copy.detailsTitle} description={copy.detailsDescription} />
          {selectedItem ? (
            <PortfolioDetail item={selectedItem} locale={locale} copy={copy} />
          ) : (
            <EmptyState
              title={hasVisibleScoredItems ? copy.detailsTitle : emptyStateTitle}
              description={hasVisibleScoredItems ? copy.noSelection : emptyStateDescription}
            />
          )}
        </Card>
      </div>
    </section>
  );
}

function PortfolioDetail({
  item,
  locale,
  copy,
}: {
  item: PortfolioItem;
  locale: Locale;
  copy: PortfolioCopy;
}) {
  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-lg font-semibold text-[var(--studio-foreground)]">{item.use_case_title}</p>
            <p className="mt-1 text-sm text-[var(--studio-muted)]">{item.program_name}</p>
          </div>
          <Badge tone={badgeToneForRisk(item.risk_profile)}>
            {copy.riskLabels[item.risk_profile] ?? item.risk_profile}
          </Badge>
        </div>
        <dl className="mt-4 grid gap-3 text-sm">
          <DetailRow label={copy.category} value={copy.categories[item.category] ?? item.category} />
          <DetailRow label={copy.businessValueScore} value={String(item.business_value_score)} />
          <DetailRow label={copy.readinessAverage} value={item.readiness_average.toFixed(2)} />
          <DetailRow label={copy.priorityScore} value={item.priority_score.toFixed(3)} />
          <DetailRow label={copy.netAnnualValue} value={formatCurrency(item.net_annual_value, locale, item.currency)} />
          <DetailRow label={copy.departmentLabel} value={item.department ?? "—"} />
          <DetailRow label={copy.statusLabel} value={formatUseCaseStatusLabel(locale, item.status)} />
          <DetailRow label={copy.confidenceLabel} value={titleCase(item.confidence_level)} />
          <DetailRow label={copy.effortLabel} value={item.effort_label_fr ?? "—"} />
          <DetailRow label={copy.updatedAt} value={formatDate(item.updated_at, locale)} />
        </dl>
      </div>

      <div className="rounded-2xl border border-[var(--studio-border)] p-4">
        <h3 className="text-base font-semibold text-[var(--studio-foreground)]">{copy.explanationTitle}</h3>
        <p className="mt-2 text-sm text-[var(--studio-muted)]">{copy.explanationDescription}</p>
        <p className="mt-4 text-sm text-[var(--studio-foreground)]">{item.category_explanation_fr}</p>
      </div>

      <Link
        href={portfolioUseCaseHref(item)}
        className="inline-flex rounded-full border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] px-4 py-2 text-sm font-medium text-[var(--studio-accent)] transition hover:border-[var(--studio-brand)] hover:text-[var(--studio-accent-hover)]"
      >
        {copy.openUseCase}
      </Link>
    </div>
  );
}

function PortfolioSvgMatrix({
  items,
  selectedUseCaseId,
  locale,
  copy,
  onSelect,
}: {
  items: PortfolioItem[];
  selectedUseCaseId: string | null;
  locale: Locale;
  copy: PortfolioCopy;
  onSelect: (useCaseId: string) => void;
}) {
  const [focusedUseCaseId, setFocusedUseCaseId] = useState<string | null>(null);

  return (
    <div className="mt-6 space-y-4">
      <p className="sr-only">{copy.matrixAriaLabel}</p>
      <svg viewBox="0 0 780 520" className="h-auto w-full max-w-full">
        <defs>
          <pattern id="risk-dots" width="8" height="8" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="1.25" fill="white" />
            <circle cx="6" cy="6" r="1.25" fill="white" />
          </pattern>
          <pattern id="risk-diagonal" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="10" stroke="white" strokeWidth="3" />
          </pattern>
          <pattern id="risk-crosshatch" width="10" height="10" patternUnits="userSpaceOnUse">
            <path d="M0 0 L10 10 M10 0 L0 10" stroke="white" strokeWidth="1.5" />
          </pattern>
        </defs>

        <rect x="80" y="40" width="620" height="360" rx="24" fill="var(--studio-surface-subtle)" />
        {[1, 2, 3, 4, 5].map((score) => {
          const x = projectX(score);
          const y = projectY(score);
          return (
            <g key={score}>
              <line x1={x} y1="60" x2={x} y2="380" stroke="var(--studio-border)" strokeDasharray="4 6" />
              <line x1="100" y1={y} x2="680" y2={y} stroke="var(--studio-border)" strokeDasharray="4 6" />
              <text x={x} y="410" textAnchor="middle" className="fill-[var(--studio-muted)] text-[12px]">
                {score}
              </text>
              <text x="70" y={y + 4} textAnchor="end" className="fill-[var(--studio-muted)] text-[12px]">
                {score}
              </text>
            </g>
          );
        })}

        <text x="390" y="448" textAnchor="middle" className="fill-[var(--studio-foreground)] text-[13px] font-semibold">
          {copy.readinessAxis}
        </text>
        <text
          x="26"
          y="220"
          textAnchor="middle"
          className="fill-[var(--studio-foreground)] text-[13px] font-semibold"
          transform="rotate(-90 26 220)"
        >
          {copy.businessValueAxis}
        </text>

        {items.map((item) => (
          <PortfolioPoint
            key={item.use_case_id}
            item={item}
            locale={locale}
            copy={copy}
            selected={item.use_case_id === selectedUseCaseId}
            focused={item.use_case_id === focusedUseCaseId}
            onSelect={() => onSelect(item.use_case_id)}
            onFocus={() => setFocusedUseCaseId(item.use_case_id)}
            onBlur={() => setFocusedUseCaseId((current) => (current === item.use_case_id ? null : current))}
          />
        ))}
      </svg>
      <div className="flex flex-wrap gap-4 text-sm">
        {(["Low", "Medium", "High", "Critical"] as const).map((risk) => (
          <div
            key={risk}
            className="flex items-center gap-3 rounded-2xl bg-[var(--studio-surface-subtle)] px-3 py-2"
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-6 w-6 shrink-0">
              {renderPointShape(shapeForRisk(risk), 12, 12, 6, {
                fill: colorForRisk(risk),
                stroke: "var(--studio-foreground)",
                strokeWidth: 1.5,
              })}
            </svg>
            <span className="text-[var(--studio-foreground)]">
              {copy.riskLabels[risk]} — {copy.riskLegendDescriptions[risk]}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function PortfolioPoint({
  item,
  locale,
  copy,
  selected,
  focused,
  onSelect,
  onFocus,
  onBlur,
}: {
  item: PortfolioItem;
  locale: Locale;
  copy: PortfolioCopy;
  selected: boolean;
  focused: boolean;
  onSelect: () => void;
  onFocus: () => void;
  onBlur: () => void;
}) {
  const size = radiusForEffort(item.effort_band);
  const x = projectX(item.matrix_x);
  const y = projectY(item.matrix_y);
  const fill = colorForRisk(item.risk_profile);
  const commonProps = {
    stroke: selected ? "var(--studio-brand)" : "var(--studio-foreground)",
    strokeWidth: selected ? 4 : 2,
  };
  return (
    <g
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      aria-label={`${item.use_case_title}, ${copy.businessValueScore} ${item.matrix_y}, ${copy.readinessAverage} ${item.matrix_x.toFixed(2)}, ${copy.netAnnualValue} ${formatCurrency(item.net_annual_value, locale, item.currency)}`}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      onFocus={onFocus}
      onBlur={onBlur}
      className="cursor-pointer outline-none"
    >
      <title>{`${item.use_case_title} · ${formatCurrency(item.net_annual_value, locale, item.currency)}`}</title>
      {focused
        ? renderPointShape(item.risk_shape, x, y, size + 8, {
            fill: "none",
            stroke: "var(--studio-brand)",
            strokeWidth: 3,
          })
        : null}
      {renderPointShape(item.risk_shape, x, y, size, { ...commonProps, fill })}
      {item.risk_pattern !== "solid"
        ? renderPointShape(item.risk_shape, x, y, size, {
            fill: patternFill(item.risk_pattern),
            stroke: "none",
            strokeWidth: 0,
          })
        : null}
    </g>
  );
}

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] p-4">
      <p className="text-xs uppercase tracking-wide text-[var(--studio-muted)]">{label}</p>
      <p className="mt-2 text-sm font-medium text-[var(--studio-foreground)]">{value}</p>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-[var(--studio-muted)]">{label}</dt>
      <dd className="text-right text-[var(--studio-foreground)]">{value}</dd>
    </div>
  );
}

function portfolioUseCaseHref(item: PortfolioItem) {
  const params = new URLSearchParams({
    workspaceId: item.workspace_id,
    programId: item.program_id,
    useCaseId: item.use_case_id,
  });
  return `/studio/use-case?${params.toString()}`;
}

function badgeToneForRisk(risk: string): "danger" | "warning" | "success" {
  if (risk === "Critical" || risk === "High") {
    return "danger";
  }
  if (risk === "Medium") {
    return "warning";
  }
  return "success";
}

function normalizeSort(value: string | null): PortfolioSort {
  if (
    value === "business-desc" ||
    value === "readiness-desc" ||
    value === "value-desc" ||
    value === "updated-desc"
  ) {
    return value;
  }
  return "business-desc";
}

function sortPortfolioItems(items: PortfolioItem[], sort: PortfolioSort) {
  const sorted = [...items];
  sorted.sort((left, right) => {
    if (sort === "readiness-desc") {
      return (
        right.readiness_average - left.readiness_average ||
        right.business_value_score - left.business_value_score
      );
    }
    if (sort === "value-desc") {
      return right.net_annual_value - left.net_annual_value || right.matrix_y - left.matrix_y;
    }
    if (sort === "updated-desc") {
      return (
        new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime() ||
        right.business_value_score - left.business_value_score
      );
    }
    return (
      right.business_value_score - left.business_value_score ||
      right.readiness_average - left.readiness_average
    );
  });
  return sorted;
}

function projectX(value: number) {
  return 100 + ((Math.max(1, Math.min(5, value)) - 1) / 4) * 580;
}

function projectY(value: number) {
  return 380 - ((Math.max(1, Math.min(5, value)) - 1) / 4) * 320;
}

function radiusForEffort(effortBand: string | null) {
  if (effortBand === "high") {
    return 22;
  }
  if (effortBand === "medium") {
    return 16;
  }
  return 11;
}

function patternFill(pattern: string) {
  if (pattern === "dots") {
    return "url(#risk-dots)";
  }
  if (pattern === "diagonal") {
    return "url(#risk-diagonal)";
  }
  if (pattern === "crosshatch") {
    return "url(#risk-crosshatch)";
  }
  return "transparent";
}

function shapeForRisk(risk: string) {
  if (risk === "Medium") {
    return "square";
  }
  if (risk === "High") {
    return "diamond";
  }
  if (risk === "Critical") {
    return "triangle";
  }
  return "circle";
}

function colorForRisk(risk: string) {
  if (risk === "Critical") {
    return "#b91c1c";
  }
  if (risk === "High") {
    return "#ef4444";
  }
  if (risk === "Medium") {
    return "#f59e0b";
  }
  return "#15803d";
}

function formatCurrency(value: number, locale: Locale, currency: string) {
  return new Intl.NumberFormat(locale === "fr" ? "fr-FR" : "en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
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

function renderPointShape(
  shape: string,
  x: number,
  y: number,
  size: number,
  props: {
    fill: string;
    stroke: string;
    strokeWidth: number;
  },
) {
  if (shape === "square") {
    return <rect x={x - size} y={y - size} width={size * 2} height={size * 2} rx="4" {...props} />;
  }
  if (shape === "diamond") {
    return (
      <polygon
        points={`${x},${y - size} ${x + size},${y} ${x},${y + size} ${x - size},${y}`}
        {...props}
      />
    );
  }
  if (shape === "triangle") {
    return (
      <polygon
        points={`${x},${y - size} ${x + size},${y + size} ${x - size},${y + size}`}
        {...props}
      />
    );
  }
  return <circle cx={x} cy={y} r={size} {...props} />;
}
