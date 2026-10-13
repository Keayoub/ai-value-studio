"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useId, useMemo, useRef, useState, type RefObject } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
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
  viewTabsLabel: string;
  matrixTitle: string;
  matrixDescription: string;
  tableTitle: string;
  tableDescription: string;
  selectedSummaryTitle: string;
  selectedSummaryDescription: string;
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
  quadrantLabels: {
    topLeft: string;
    topRight: string;
    bottomLeft: string;
    bottomRight: string;
  };
  confidenceLevels: Record<string, string>;
  effortLegendLabels: Record<"low" | "medium" | "high", string>;
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
type MatrixDimensions = {
  width: number;
  height: number;
  plotLeft: number;
  plotTop: number;
  plotWidth: number;
  plotHeight: number;
  plotRight: number;
  plotBottom: number;
};
type LaidOutPortfolioPoint = {
  item: PortfolioItem;
  x: number;
  y: number;
  size: number;
};

const MATRIX_MIN_HEIGHT = 300;
const MATRIX_DEFAULT_WIDTH = 720;
const TOUCH_TARGET_RADIUS = 22;
const GOLDEN_ANGLE_RADIANS = 2.399963229728653;
const portfolioTitleCollator = new Intl.Collator("fr", { sensitivity: "base" });

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
    toggleTable: "Vue liste",
    viewTabsLabel: "Choisir la représentation du portefeuille",
    matrixTitle: "Positionnement portefeuille",
    matrixDescription:
      "Chaque point reste sélectionnable au clavier comme au toucher, avec un résumé textuel synchronisé.",
    tableTitle: "Liste portefeuille",
    tableDescription:
      "La liste reprend exactement les mêmes cas d’usage que la matrice et ajoute un tri dédié.",
    selectedSummaryTitle: "Résumé synchronisé",
    selectedSummaryDescription:
      "La sélection active reste partagée entre la matrice, la liste et le panneau de détail.",
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
    sortLabel: "Tri de la liste",
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
    quadrantLabels: {
      topLeft: "Paris stratégiques",
      topRight: "Quick wins",
      bottomLeft: "À différer / réévaluer",
      bottomRight: "Fondations",
    },
    confidenceLevels: {
      low: "Faible",
      medium: "Moyenne",
      high: "Élevée",
    },
    effortLegendLabels: {
      low: "Effort faible",
      medium: "Effort moyen",
      high: "Effort élevé",
    },
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
    toggleTable: "List view",
    viewTabsLabel: "Choose the portfolio representation",
    matrixTitle: "Portfolio positioning",
    matrixDescription:
      "Each point remains keyboard and touch reachable, with a synchronized text summary.",
    tableTitle: "Portfolio list",
    tableDescription:
      "The list mirrors the exact same use cases as the matrix and adds dedicated sorting.",
    selectedSummaryTitle: "Synchronized summary",
    selectedSummaryDescription:
      "The active selection stays shared across the matrix, the list, and the detail panel.",
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
    sortLabel: "List sort",
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
    quadrantLabels: {
      topLeft: "High value · lower readiness",
      topRight: "High value · higher readiness",
      bottomLeft: "Lower value · lower readiness",
      bottomRight: "Lower value · higher readiness",
    },
    confidenceLevels: {
      low: "Low",
      medium: "Medium",
      high: "High",
    },
    effortLegendLabels: {
      low: "Low effort",
      medium: "Medium effort",
      high: "High effort",
    },
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
  const portfolioViewId = useId();

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
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
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

  const allItems = useMemo(() => portfolio?.items ?? [], [portfolio?.items]);
  const sortedItems = useMemo(() => sortPortfolioItems(allItems, sort), [allItems, sort]);
  const selectedItem =
    allItems.find((item) => item.use_case_id === selectedUseCaseId) ?? sortedItems[0] ?? null;
  const availablePrograms = useMemo(() => {
    const visibleIds = new Set(visiblePrograms.map((program) => program.id));
    return (portfolio?.available_filters.programs ?? []).filter((program) => visibleIds.has(program.id));
  }, [portfolio?.available_filters.programs, visiblePrograms]);
  const hasActiveFilters = Boolean(
    filters.programId || filters.status || filters.department || filters.risk,
  );
  const hasVisibleScoredItems = allItems.length > 0;

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
              <Button variant="secondary" onClick={resetFilters}>
                {copy.clearFilters}
              </Button>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.25fr,0.75fr]">
        <div className="min-w-0">
          <Card>
          <CardHeader
            title={view === "matrix" ? copy.matrixTitle : copy.tableTitle}
            description={view === "matrix" ? copy.matrixDescription : copy.tableDescription}
          />
            <div className="space-y-4">
              <PortfolioViewTabs
                copy={copy}
                view={view}
                baseId={portfolioViewId}
                onViewChange={(nextView) => updateQuery({ portfolioView: nextView })}
              />
              <div className="flex flex-wrap items-end justify-between gap-4">
                <p className="text-sm text-[var(--studio-muted)]">{copy.explanationHint}</p>
                {view === "table" ? (
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
                ) : null}
              </div>
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
              baseId={portfolioViewId}
              items={allItems}
              selectedUseCaseId={selectedItem?.use_case_id ?? null}
              locale={locale}
              copy={copy}
              onSelect={setSelectedUseCaseId}
            />
          ) : (
            <PortfolioListView
              baseId={portfolioViewId}
              items={sortedItems}
              selectedUseCaseId={selectedItem?.use_case_id ?? null}
              locale={locale}
              copy={copy}
              onSelect={setSelectedUseCaseId}
            />
          )}
            {selectedItem ? (
              <SelectedPortfolioSummary item={selectedItem} locale={locale} copy={copy} />
            ) : null}
          </Card>
        </div>

        <div className="min-w-0">
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
      </div>
    </section>
  );
}

function PortfolioViewTabs({
  copy,
  baseId,
  view,
  onViewChange,
}: {
  copy: PortfolioCopy;
  baseId: string;
  view: PortfolioView;
  onViewChange: (view: PortfolioView) => void;
}) {
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const views: Array<{ view: PortfolioView; label: string }> = [
    { view: "matrix", label: copy.toggleMatrix },
    { view: "table", label: copy.toggleTable },
  ];

  return (
    <div>
      <div
        role="tablist"
        aria-label={copy.viewTabsLabel}
        className="inline-flex flex-wrap gap-2 rounded-full border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] p-1"
      >
        {views.map((option, index) => {
          const selected = option.view === view;
          const tabId = `${baseId}-${option.view}-tab`;
          const panelId = `${baseId}-${option.view}-panel`;
          return (
            <button
              key={option.view}
              ref={(element) => {
                tabRefs.current[index] = element;
              }}
              id={tabId}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={panelId}
              tabIndex={selected ? 0 : -1}
              className={[
                "rounded-full px-4 py-2 text-sm font-medium transition",
                selected
                  ? "bg-[var(--studio-brand)] text-white"
                  : "text-[var(--studio-foreground)] hover:bg-[var(--studio-surface)]",
              ].join(" ")}
              onClick={() => onViewChange(option.view)}
              onKeyDown={(event) => {
                let nextIndex: number | null = null;
                if (event.key === "ArrowRight" || event.key === "ArrowDown") {
                  nextIndex = (index + 1) % views.length;
                } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
                  nextIndex = (index - 1 + views.length) % views.length;
                } else if (event.key === "Home") {
                  nextIndex = 0;
                } else if (event.key === "End") {
                  nextIndex = views.length - 1;
                }
                if (nextIndex === null) {
                  return;
                }
                event.preventDefault();
                onViewChange(views[nextIndex].view);
                tabRefs.current[nextIndex]?.focus();
              }}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SelectedPortfolioSummary({
  item,
  locale,
  copy,
}: {
  item: PortfolioItem;
  locale: Locale;
  copy: PortfolioCopy;
}) {
  return (
    <div
      data-portfolio-summary=""
      aria-live="polite"
      aria-atomic="true"
      className="mt-6 rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] p-4"
    >
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--studio-muted)]">
        {copy.selectedSummaryTitle}
      </p>
      <p className="mt-1 text-sm text-[var(--studio-muted)]">{copy.selectedSummaryDescription}</p>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-[var(--studio-foreground)]">
            {item.use_case_title}
          </p>
          <p className="mt-1 text-sm text-[var(--studio-muted)]">{item.program_name}</p>
        </div>
        <Badge tone={badgeToneForRisk(item.risk_profile)}>
          {copy.riskLabels[item.risk_profile] ?? item.risk_profile}
        </Badge>
      </div>
      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
        <DetailRow label={copy.category} value={copy.categories[item.category] ?? item.category} />
        <DetailRow label={copy.netAnnualValue} value={formatCurrency(item.net_annual_value, locale, item.currency)} />
        <DetailRow label={copy.readinessAverage} value={item.readiness_average.toFixed(2)} />
        <DetailRow label={copy.businessValueScore} value={String(item.business_value_score)} />
        <DetailRow label={copy.effortLabel} value={item.effort_label_fr ?? "—"} />
        <DetailRow label={copy.confidenceLabel} value={formatConfidenceLabel(item.confidence_level, copy)} />
      </dl>
      <Link
        href={portfolioUseCaseHref(item)}
        className="mt-4 inline-flex rounded-full border border-[var(--studio-border)] bg-[var(--studio-surface)] px-4 py-2 text-sm font-medium text-[var(--studio-accent)] transition hover:border-[var(--studio-brand)] hover:text-[var(--studio-accent-hover)]"
      >
        {copy.openUseCase}
      </Link>
    </div>
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
          <DetailRow label={copy.confidenceLabel} value={formatConfidenceLabel(item.confidence_level, copy)} />
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
  baseId,
  items,
  selectedUseCaseId,
  locale,
  copy,
  onSelect,
}: {
  baseId: string;
  items: PortfolioItem[];
  selectedUseCaseId: string | null;
  locale: Locale;
  copy: PortfolioCopy;
  onSelect: (useCaseId: string) => void;
}) {
  const [focusedUseCaseId, setFocusedUseCaseId] = useState<string | null>(null);
  const frameRef = useRef<HTMLDivElement | null>(null);
  const dimensions = useResponsiveMatrixDimensions(frameRef);
  const laidOutItems = useMemo(
    () => layoutPortfolioPoints(items, dimensions),
    [dimensions, items],
  );
  const legendEntries = useMemo(
    () => (["low", "medium", "high"] as const).map((effort) => ({
      effort,
      radius: radiusForEffort(effort),
      label: copy.effortLegendLabels[effort],
    })),
    [copy.effortLegendLabels],
  );
  const tabPanelId = `${baseId}-matrix-panel`;

  return (
    <div id={tabPanelId} role="tabpanel" aria-labelledby={`${baseId}-matrix-tab`} className="mt-6 space-y-4">
      <p className="sr-only">{copy.matrixAriaLabel}</p>
      <div
        ref={frameRef}
        data-portfolio-matrix-frame=""
        className="relative w-full overflow-hidden rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] p-3 sm:p-4"
      >
        <svg
          width={dimensions.width}
          height={dimensions.height}
          viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
          className="block h-auto w-full"
        >
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

          <rect
            x={dimensions.plotLeft}
            y={dimensions.plotTop}
            width={dimensions.plotWidth}
            height={dimensions.plotHeight}
            rx="24"
            fill="var(--studio-surface)"
          />
          {[1, 2, 3, 4, 5].map((score) => {
            const x = projectX(score, dimensions);
            const y = projectY(score, dimensions);
            return (
              <g key={score}>
                <line
                  x1={x}
                  y1={dimensions.plotTop}
                  x2={x}
                  y2={dimensions.plotBottom}
                  stroke="var(--studio-border)"
                  strokeDasharray="4 6"
                />
                <line
                  x1={dimensions.plotLeft}
                  y1={y}
                  x2={dimensions.plotRight}
                  y2={y}
                  stroke="var(--studio-border)"
                  strokeDasharray="4 6"
                />
                <text
                  x={x}
                  y={dimensions.plotBottom + 28}
                  textAnchor="middle"
                  fill="var(--studio-muted)"
                  fontSize="12"
                >
                  {score}
                </text>
                <text
                  x={dimensions.plotLeft - 18}
                  y={y + 4}
                  textAnchor="end"
                  fill="var(--studio-muted)"
                  fontSize="12"
                >
                  {score}
                </text>
              </g>
            );
          })}

          <text
            x={dimensions.plotLeft + dimensions.plotWidth / 2}
            y={dimensions.height - 16}
            textAnchor="middle"
            fill="var(--studio-foreground)"
            fontSize="13"
            fontWeight="600"
          >
            {copy.readinessAxis}
          </text>
          <text
            x="18"
            y={dimensions.plotTop + dimensions.plotHeight / 2}
            textAnchor="middle"
            fill="var(--studio-foreground)"
            fontSize="13"
            fontWeight="600"
            transform={`rotate(-90 18 ${dimensions.plotTop + dimensions.plotHeight / 2})`}
          >
            {copy.businessValueAxis}
          </text>

          {laidOutItems.map((point) => (
            <PortfolioPoint
              key={point.item.use_case_id}
              point={point}
              locale={locale}
              copy={copy}
              selected={point.item.use_case_id === selectedUseCaseId}
              focused={point.item.use_case_id === focusedUseCaseId}
              onSelect={() => onSelect(point.item.use_case_id)}
              onFocus={() => setFocusedUseCaseId(point.item.use_case_id)}
              onBlur={() =>
                setFocusedUseCaseId((current) =>
                  current === point.item.use_case_id ? null : current,
                )
              }
            />
          ))}
        </svg>

        <div
          data-portfolio-quadrant="top-left"
          className="pointer-events-none absolute left-2 top-6 max-w-[calc(50%-0.5rem)] rounded-md px-1 py-2 text-[12px] font-medium leading-4 text-[var(--studio-foreground)] shadow-sm sm:left-6 sm:max-w-[42%] sm:px-3"
          style={{ backgroundColor: "color-mix(in srgb, var(--studio-surface) 88%, transparent)" }}
        >
          {copy.quadrantLabels.topLeft}
        </div>
        <div
          data-portfolio-quadrant="top-right"
          className="pointer-events-none absolute right-2 top-6 max-w-[calc(50%-0.5rem)] rounded-md px-1 py-2 text-right text-[12px] font-medium leading-4 text-[var(--studio-foreground)] shadow-sm sm:right-6 sm:max-w-[42%] sm:px-3"
          style={{ backgroundColor: "color-mix(in srgb, var(--studio-surface) 88%, transparent)" }}
        >
          {copy.quadrantLabels.topRight}
        </div>
        <div
          data-portfolio-quadrant="bottom-left"
          className="pointer-events-none absolute bottom-24 left-2 max-w-[calc(50%-0.5rem)] rounded-md px-1 py-2 text-[12px] font-medium leading-4 text-[var(--studio-foreground)] shadow-sm sm:left-6 sm:max-w-[42%] sm:px-3"
          style={{ backgroundColor: "color-mix(in srgb, var(--studio-surface) 88%, transparent)" }}
        >
          {copy.quadrantLabels.bottomLeft}
        </div>
        <div
          data-portfolio-quadrant="bottom-right"
          className="pointer-events-none absolute bottom-24 right-2 max-w-[calc(50%-0.5rem)] rounded-md px-1 py-2 text-right text-[12px] font-medium leading-4 text-[var(--studio-foreground)] shadow-sm sm:right-6 sm:max-w-[42%] sm:px-3"
          style={{ backgroundColor: "color-mix(in srgb, var(--studio-surface) 88%, transparent)" }}
        >
          {copy.quadrantLabels.bottomRight}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
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
        <div className="rounded-2xl bg-[var(--studio-surface-subtle)] px-4 py-3">
          <p className="text-sm font-semibold text-[var(--studio-foreground)]">{copy.legendEffort}</p>
          <div className="mt-3 flex flex-wrap items-center gap-5 text-sm text-[var(--studio-foreground)]">
            {legendEntries.map((entry) => (
              <div key={entry.effort} className="flex items-center gap-3">
                <svg aria-hidden="true" width="44" height="44" viewBox="0 0 44 44" className="shrink-0">
                  <circle cx="22" cy="22" r={Math.min(entry.radius, 16)} fill="var(--studio-brand)" opacity="0.2" />
                  <circle cx="22" cy="22" r={Math.min(entry.radius, 16)} fill="none" stroke="var(--studio-brand)" strokeWidth="2" />
                </svg>
                <span>{entry.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function PortfolioPoint({
  point,
  locale,
  copy,
  selected,
  focused,
  onSelect,
  onFocus,
  onBlur,
}: {
  point: LaidOutPortfolioPoint;
  locale: Locale;
  copy: PortfolioCopy;
  selected: boolean;
  focused: boolean;
  onSelect: () => void;
  onFocus: () => void;
  onBlur: () => void;
}) {
  const { item, size, x, y } = point;
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
      <circle cx={x} cy={y} r={Math.max(size + 6, TOUCH_TARGET_RADIUS)} fill="transparent" />
      {selected
        ? renderPointShape(item.risk_shape, x, y, size + 10, {
            fill: "none",
            stroke: "var(--studio-brand)",
            strokeWidth: 4,
          })
        : null}
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

function PortfolioListView({
  baseId,
  items,
  selectedUseCaseId,
  locale,
  copy,
  onSelect,
}: {
  baseId: string;
  items: PortfolioItem[];
  selectedUseCaseId: string | null;
  locale: Locale;
  copy: PortfolioCopy;
  onSelect: (useCaseId: string) => void;
}) {
  return (
    <div id={`${baseId}-table-panel`} role="tabpanel" aria-labelledby={`${baseId}-table-tab`} className="mt-6">
      <ul className="grid gap-3">
        {items.map((item) => {
          const selected = item.use_case_id === selectedUseCaseId;
          return (
            <li
              key={item.use_case_id}
              data-portfolio-record={item.use_case_id}
              className={[
                "rounded-2xl border p-4 transition",
                selected
                  ? "border-[var(--studio-brand)] bg-[var(--studio-surface-subtle)] shadow-sm"
                  : "border-[var(--studio-border)] bg-[var(--studio-surface)]",
              ].join(" ")}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <button
                    type="button"
                    aria-pressed={selected}
                    className="text-left text-base font-semibold text-[var(--studio-accent)] underline underline-offset-2"
                    onClick={() => onSelect(item.use_case_id)}
                  >
                    {item.use_case_title}
                  </button>
                  <p className="mt-1 text-sm text-[var(--studio-muted)]">{item.program_name}</p>
                </div>
                <Badge tone={badgeToneForRisk(item.risk_profile)}>
                  {copy.riskLabels[item.risk_profile] ?? item.risk_profile}
                </Badge>
              </div>
              <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                <DetailRow label={copy.category} value={copy.categories[item.category] ?? item.category} />
                <DetailRow label={copy.riskProfile} value={copy.riskLabels[item.risk_profile] ?? item.risk_profile} />
                <DetailRow label={copy.netAnnualValue} value={formatCurrency(item.net_annual_value, locale, item.currency)} />
                <DetailRow label={copy.readinessAverage} value={item.readiness_average.toFixed(2)} />
                <DetailRow label={copy.effortLabel} value={item.effort_label_fr ?? "—"} />
              </dl>
              <div className="mt-4 flex flex-wrap gap-3">
                <Button
                  variant={selected ? "primary" : "secondary"}
                  onClick={() => onSelect(item.use_case_id)}
                >
                  {copy.detailsTitle}
                </Button>
                <Link
                  href={portfolioUseCaseHref(item)}
                  className="inline-flex rounded-full border border-[var(--studio-border)] px-4 py-2 text-sm font-medium text-[var(--studio-accent)] transition hover:border-[var(--studio-brand)] hover:text-[var(--studio-accent-hover)]"
                >
                  {copy.openUseCase}
                </Link>
              </div>
            </li>
          );
        })}
      </ul>
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
        right.business_value_score - left.business_value_score ||
        stablePortfolioTieBreak(left, right)
      );
    }
    if (sort === "value-desc") {
      return (
        right.net_annual_value - left.net_annual_value ||
        right.matrix_y - left.matrix_y ||
        stablePortfolioTieBreak(left, right)
      );
    }
    if (sort === "updated-desc") {
      return (
        new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime() ||
        right.business_value_score - left.business_value_score ||
        stablePortfolioTieBreak(left, right)
      );
    }
    return (
      right.business_value_score - left.business_value_score ||
      right.readiness_average - left.readiness_average ||
      stablePortfolioTieBreak(left, right)
    );
  });
  return sorted;
}

function useResponsiveMatrixDimensions(containerRef: RefObject<HTMLDivElement | null>) {
  const [containerWidth, setContainerWidth] = useState(MATRIX_DEFAULT_WIDTH);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const updateWidth = () => {
      const nextWidth = Math.max(Math.floor(container.clientWidth) - 24, 280);
      setContainerWidth((current) => (current === nextWidth ? current : nextWidth));
    };
    updateWidth();
    const observer = new ResizeObserver(() => {
      updateWidth();
    });
    observer.observe(container);
    return () => {
      observer.disconnect();
    };
  }, [containerRef]);

  return useMemo(() => createMatrixDimensions(containerWidth), [containerWidth]);
}

function createMatrixDimensions(width: number): MatrixDimensions {
  const safeWidth = Math.max(width, 280);
  const compact = safeWidth < 420;
  const plotLeft = compact ? 56 : 76;
  const plotTop = 52;
  const plotRightPadding = compact ? 20 : 32;
  const plotBottomPadding = compact ? 92 : 96;
  const plotWidth = Math.max(safeWidth - plotLeft - plotRightPadding, 180);
  const plotHeight = Math.max(Math.round(plotWidth * 0.6), MATRIX_MIN_HEIGHT - plotTop - plotBottomPadding);
  const height = Math.max(MATRIX_MIN_HEIGHT, plotTop + plotHeight + plotBottomPadding);

  return {
    width: safeWidth,
    height,
    plotLeft,
    plotTop,
    plotWidth,
    plotHeight,
    plotRight: plotLeft + plotWidth,
    plotBottom: plotTop + plotHeight,
  };
}

function layoutPortfolioPoints(
  items: PortfolioItem[],
  dimensions: MatrixDimensions,
): LaidOutPortfolioPoint[] {
  const orderedItems = [...items].sort((left, right) => stablePortfolioTieBreak(left, right));
  const clusters = new Map<string, PortfolioItem[]>();
  for (const item of orderedItems) {
    const key = matrixClusterKey(item, dimensions);
    const current = clusters.get(key);
    if (current) {
      current.push(item);
    } else {
      clusters.set(key, [item]);
    }
  }

  return orderedItems.map((item) => {
    const size = radiusForEffort(item.effort_band);
    const baseX = projectX(item.matrix_x, dimensions);
    const baseY = projectY(item.matrix_y, dimensions);
    const clusterKey = matrixClusterKey(item, dimensions);
    const clusterItems = clusters.get(clusterKey) ?? [item];
    const clusterIndex = clusterItems.findIndex(
      (clusterItem) => clusterItem.use_case_id === item.use_case_id,
    );
    const { dx, dy } = deterministicClusterOffset(clusterKey, clusterIndex, clusterItems.length, size);

    return {
      item,
      x: clamp(baseX + dx, dimensions.plotLeft + TOUCH_TARGET_RADIUS, dimensions.plotRight - TOUCH_TARGET_RADIUS),
      y: clamp(baseY + dy, dimensions.plotTop + TOUCH_TARGET_RADIUS, dimensions.plotBottom - TOUCH_TARGET_RADIUS),
      size,
    };
  });
}

function matrixClusterKey(item: PortfolioItem, dimensions: MatrixDimensions) {
  const quantizedX = Math.round((projectX(item.matrix_x, dimensions) - dimensions.plotLeft) / 28);
  const quantizedY = Math.round((projectY(item.matrix_y, dimensions) - dimensions.plotTop) / 28);
  return `${quantizedX}:${quantizedY}`;
}

function deterministicClusterOffset(clusterKey: string, index: number, total: number, size: number) {
  if (total <= 1 || index === 0) {
    return { dx: 0, dy: 0 };
  }
  const phase = hashString(clusterKey) % 360;
  const radius = Math.max(size + 10, 18) * Math.sqrt(index);
  const angle = ((phase / 180) * Math.PI) + ((index - 1) * GOLDEN_ANGLE_RADIANS);
  return {
    dx: Math.cos(angle) * radius,
    dy: Math.sin(angle) * radius,
  };
}

function stablePortfolioTieBreak(left: PortfolioItem, right: PortfolioItem) {
  return (
    portfolioTitleCollator.compare(left.use_case_title, right.use_case_title) ||
    portfolioTitleCollator.compare(left.program_name, right.program_name) ||
    left.use_case_id.localeCompare(right.use_case_id)
  );
}

function hashString(value: string) {
  let hash = 0;
  for (const character of value) {
    hash = ((hash << 5) - hash + character.charCodeAt(0)) | 0;
  }
  return Math.abs(hash);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function projectX(value: number, dimensions: MatrixDimensions) {
  return dimensions.plotLeft + ((Math.max(1, Math.min(5, value)) - 1) / 4) * dimensions.plotWidth;
}

function projectY(value: number, dimensions: MatrixDimensions) {
  return dimensions.plotBottom - ((Math.max(1, Math.min(5, value)) - 1) / 4) * dimensions.plotHeight;
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

function formatConfidenceLabel(value: string, copy: PortfolioCopy) {
  const normalized = value.toLowerCase();
  return copy.confidenceLevels[normalized] ?? titleCase(value);
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
