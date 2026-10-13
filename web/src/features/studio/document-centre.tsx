"use client";

import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  ApiClientError,
  BrowserApiClient,
} from "@/features/api/browser-api-client";
import type {
  DocumentFormat,
  DocumentStatus,
  DocumentType,
  GeneratedDocument,
  GeneratedDocumentVersion,
  ReviewStatus,
  UseCase,
  WorkspaceRole,
} from "@/features/api/types";
import { useAuth } from "@/features/auth/auth-context";
import { getPublicRuntimeConfig } from "@/features/auth/runtime";
import { cn } from "@/lib/cn";

const runtimeConfig = getPublicRuntimeConfig(process.env);

type Locale = "fr" | "en";

const documentCentreCopy = {
  fr: {
    title: "Centre documentaire",
    description:
      "Générez des versions immuables des notes exécutives et chartes pilotes à partir des versions verrouillées de l’évaluation, du scorecard et de la revue sponsor.",
    loading: "Chargement du centre documentaire…",
    emptyTitle: "Aucun document généré",
    emptyDescription:
      "Le brouillon Markdown devient disponible après verrouillage de l’évaluation, recalcul du scorecard et soumission de la revue. Le PDF nécessite une revue sponsor approuvée.",
    loadErrorTitle: "Impossible de charger le centre documentaire.",
    retry: "Réessayer",
    generateMarkdown: "Générer Markdown",
    generatePdf: "Générer PDF",
    download: "Télécharger",
    downloadCurrentAria: (typeLabel: string) => `Télécharger la version courante de ${typeLabel}`,
    downloadVersionAria: (typeLabel: string, versionNo: number) =>
      `Télécharger ${typeLabel} version ${versionNo}`,
    approve: "Approuver le document",
    approveCurrentAria: (typeLabel: string) => `Approuver la version courante de ${typeLabel}`,
    versionsSource: "Versions source",
    currentVersion: "Version courante",
    versionHistory: "Historique des versions",
    version: "Version",
    status: "Statut",
    format: "Format",
    createdAt: "Généré le",
    createdBy: "Auteur",
    approval: "Approbation",
    aiSections: "Sections assistées par l’IA",
    metadataChanges: "Évolutions",
    sha: "SHA-256",
    noData: "—",
    approvalPending: "En attente d’approbation sponsor",
    alreadyApproved: "Version approuvée",
    approvedOnly: "Les sponsors peuvent télécharger uniquement les versions approuvées.",
    approvalUnavailable:
      "L’approbation sponsor n’est disponible que pour une version courante issue d’une revue approuvée.",
    types: {
      ExecutiveBrief: "Note exécutive",
      PilotCharter: "Charte pilote",
      AMOAImplementationPlan: "Plan d’implémentation AMOA",
    } satisfies Record<DocumentType, string>,
    documentStatuses: {
      Draft: "Brouillon",
      InReview: "En validation",
      Approved: "Approuvé",
      Superseded: "Remplacé",
    } satisfies Record<DocumentStatus, string>,
    reviewStatuses: {
      Submitted: "Soumise",
      ChangesRequested: "Changements demandés",
      Approved: "Approuvée",
      Rejected: "Rejetée",
    } satisfies Record<ReviewStatus, string>,
    formats: {
      markdown: "Markdown",
      pdf: "PDF",
    } satisfies Record<DocumentFormat, string>,
    metadataDiffs: {
      "assessment-version": "Version d’évaluation",
      "scorecard-version": "Version du scorecard",
      "review-status": "Statut de revue",
      "artifact-sha256": "Empreinte du document",
    } satisfies Record<string, string>,
    toasts: {
      generated: "Document généré",
      downloaded: "Téléchargement prêt",
      approved: "Document approuvé",
    },
  },
  en: {
    title: "Document centre",
    description:
      "Generate immutable executive briefs and pilot charters from locked assessment, scorecard, and sponsor review versions.",
    loading: "Loading document centre…",
    emptyTitle: "No generated document",
    emptyDescription:
      "Markdown drafts become available after the assessment is locked, the scorecard is recalculated, and the review is submitted. PDF generation requires an approved sponsor review.",
    loadErrorTitle: "Could not load the document centre.",
    retry: "Retry",
    generateMarkdown: "Generate Markdown",
    generatePdf: "Generate PDF",
    download: "Download",
    downloadCurrentAria: (typeLabel: string) => `Download current ${typeLabel}`,
    downloadVersionAria: (typeLabel: string, versionNo: number) =>
      `Download ${typeLabel} version ${versionNo}`,
    approve: "Approve document",
    approveCurrentAria: (typeLabel: string) => `Approve current ${typeLabel}`,
    versionsSource: "Source versions",
    currentVersion: "Current version",
    versionHistory: "Version history",
    version: "Version",
    status: "Status",
    format: "Format",
    createdAt: "Generated on",
    createdBy: "Author",
    approval: "Approval",
    aiSections: "AI-assisted sections",
    metadataChanges: "Changes",
    sha: "SHA-256",
    noData: "—",
    approvalPending: "Pending sponsor approval",
    alreadyApproved: "Approved version",
    approvedOnly: "Sponsors can download approved versions only.",
    approvalUnavailable:
      "Sponsor approval is available only for the current version when it comes from an approved review.",
    types: {
      ExecutiveBrief: "Executive Brief",
      PilotCharter: "Pilot Charter",
      AMOAImplementationPlan: "AMOA Implementation Plan",
    } satisfies Record<DocumentType, string>,
    documentStatuses: {
      Draft: "Draft",
      InReview: "In review",
      Approved: "Approved",
      Superseded: "Superseded",
    } satisfies Record<DocumentStatus, string>,
    reviewStatuses: {
      Submitted: "Submitted",
      ChangesRequested: "Changes requested",
      Approved: "Approved",
      Rejected: "Rejected",
    } satisfies Record<ReviewStatus, string>,
    formats: {
      markdown: "Markdown",
      pdf: "PDF",
    } satisfies Record<DocumentFormat, string>,
    metadataDiffs: {
      "assessment-version": "Assessment version",
      "scorecard-version": "Scorecard version",
      "review-status": "Review status",
      "artifact-sha256": "Document fingerprint",
    } satisfies Record<string, string>,
    toasts: {
      generated: "Document generated",
      downloaded: "Download ready",
      approved: "Document approved",
    },
  },
} as const;

function problemMessage(error: unknown, fallback: string) {
  if (error instanceof ApiClientError) {
    return error.problem.detail;
  }
  return error instanceof Error ? error.message : fallback;
}

function badgeTone(status: DocumentStatus) {
  if (status === "Approved") {
    return "success" as const;
  }
  if (status === "InReview") {
    return "info" as const;
  }
  return "warning" as const;
}

function mergeDocument(current: GeneratedDocument[], next: GeneratedDocument) {
  const hasMatch = current.some(
    (document) =>
      document.type === next.type || (document.id !== null && document.id === next.id),
  );
  if (!hasMatch) {
    return [...current, next];
  }
  return current.map((document) =>
    document.type === next.type || (document.id !== null && document.id === next.id)
      ? next
      : document,
  );
}

function versionStatus(version: GeneratedDocumentVersion): DocumentStatus {
  if (version.approved_at) {
    return "Approved";
  }
  return version.source_review_status === "Approved" ? "InReview" : "Draft";
}

function labelForType(type: DocumentType, locale: Locale) {
  return documentCentreCopy[locale].types[type];
}

function formatDocumentStatusLabel(status: DocumentStatus, locale: Locale) {
  return documentCentreCopy[locale].documentStatuses[status];
}

function formatReviewStatusLabel(status: ReviewStatus, locale: Locale) {
  return documentCentreCopy[locale].reviewStatuses[status];
}

function formatDocumentFormatLabel(format: DocumentFormat, locale: Locale) {
  return documentCentreCopy[locale].formats[format];
}

function formatMetadataDiffLabel(code: string, locale: Locale) {
  const localized = (documentCentreCopy[locale].metadataDiffs as Record<string, string>)[code];
  if (localized) {
    return localized;
  }
  return code.replaceAll("-", " ");
}

function formatDateTime(value: string | null, locale: Locale, empty: string) {
  if (!value) {
    return empty;
  }
  return new Intl.DateTimeFormat(locale === "fr" ? "fr-CA" : "en-CA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatAiSectionsCount(count: number, locale: Locale) {
  if (locale === "fr") {
    return `${count} section${count > 1 ? "s" : ""}`;
  }
  return `${count} section${count === 1 ? "" : "s"}`;
}

function formatVersionSource(
  version: Pick<
    GeneratedDocumentVersion,
    "source_assessment_version_no" | "source_scorecard_version_no" | "source_review_status"
  >,
  locale: Locale,
) {
  const reviewLabel = formatReviewStatusLabel(version.source_review_status, locale);
  if (locale === "fr") {
    return `Évaluation v${version.source_assessment_version_no} · Scorecard v${version.source_scorecard_version_no} · Revue ${reviewLabel}`;
  }
  return `Assessment v${version.source_assessment_version_no} · Scorecard v${version.source_scorecard_version_no} · Review ${reviewLabel}`;
}

function formatEligibilitySource(document: GeneratedDocument, locale: Locale, empty: string) {
  const reviewStatus = document.eligibility.source_review_status;
  const reviewLabel = reviewStatus ? formatReviewStatusLabel(reviewStatus, locale) : empty;
  if (locale === "fr") {
    return `Évaluation v${document.eligibility.source_assessment_version ?? "?"} · Scorecard v${document.eligibility.source_scorecard_version ?? "?"} · Revue ${reviewLabel}`;
  }
  return `Assessment v${document.eligibility.source_assessment_version ?? "?"} · Scorecard v${document.eligibility.source_scorecard_version ?? "?"} · Review ${reviewLabel}`;
}

function formatApprovalLabel(
  version: GeneratedDocumentVersion,
  locale: Locale,
  empty: string,
) {
  const copy = documentCentreCopy[locale];
  if (!version.approved_at) {
    return copy.approvalPending;
  }
  const approvedAt = formatDateTime(version.approved_at, locale, empty);
  const approver = version.approved_by_subject_id ?? empty;
  return `${approvedAt} · ${approver}`;
}

function currentVersionDownloadReason(
  viewerRole: WorkspaceRole | string | null,
  version: GeneratedDocumentVersion | null,
  locale: Locale,
) {
  if (viewerRole === "Sponsor" && version && !version.approved_at) {
    return documentCentreCopy[locale].approvedOnly;
  }
  return null;
}

function currentApprovalReason(document: GeneratedDocument, locale: Locale) {
  const copy = documentCentreCopy[locale];
  if (!document.current_version || !document.id) {
    return null;
  }
  if (document.status === "Approved") {
    return copy.alreadyApproved;
  }
  if (
    document.status !== "InReview" ||
    document.current_version.source_review_status !== "Approved"
  ) {
    return copy.approvalUnavailable;
  }
  return null;
}

type ActionButtonProps = {
  label: string;
  ariaLabel?: string;
  descriptionId?: string;
  description?: string | null;
  busy?: boolean;
  onClick: () => void;
  variant?: "primary" | "secondary" | "ghost" | "danger";
};

function ActionButton({
  label,
  ariaLabel,
  descriptionId,
  description,
  busy = false,
  onClick,
  variant = "primary",
}: ActionButtonProps) {
  const unavailable = Boolean(description);
  return (
    <div className="max-w-full space-y-1">
      <Button
        variant={variant}
        aria-label={ariaLabel}
        aria-describedby={description && descriptionId ? descriptionId : undefined}
        aria-disabled={unavailable || undefined}
        disabled={busy}
        className={cn(unavailable && "cursor-not-allowed opacity-50")}
        onClick={(event) => {
          if (busy || unavailable) {
            event.preventDefault();
            return;
          }
          onClick();
        }}
      >
        {label}
      </Button>
      {description && descriptionId ? (
        <p
          id={descriptionId}
          className="max-w-72 text-xs leading-5 text-[var(--studio-muted)]"
        >
          {description}
        </p>
      ) : null}
    </div>
  );
}

function DocumentCentreLoading({ copy }: { copy: (typeof documentCentreCopy)[Locale] }) {
  return (
    <div className="space-y-4">
      <p aria-live="polite" className="sr-only">
        {copy.loading}
      </p>
      {[0, 1].map((item) => (
        <div
          key={item}
          aria-hidden="true"
          className="rounded-2xl border border-[var(--studio-border)] p-4"
        >
          <div className="flex flex-col gap-3 border-b border-[var(--studio-border)] pb-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-2">
              <Skeleton className="h-5 w-44" />
              <Skeleton className="h-4 w-72 max-w-full" />
            </div>
            <div className="flex flex-wrap gap-2">
              <Skeleton className="h-10 w-36" />
              <Skeleton className="h-10 w-28" />
            </div>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        </div>
      ))}
    </div>
  );
}

function Info({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="min-w-0">
      <p className="text-xs uppercase tracking-wide text-[var(--studio-muted)]">{label}</p>
      <p
        className={cn(
          "mt-1 break-words text-sm text-[var(--studio-foreground)]",
          mono && "font-mono text-xs sm:text-sm",
        )}
      >
        {value}
      </p>
    </div>
  );
}

export function DocumentCentre({
  workspaceId,
  programId,
  programSponsorMembershipId,
  useCase,
  locale,
  viewerRole,
}: {
  workspaceId: string;
  programId: string;
  programSponsorMembershipId: string | null;
  useCase: UseCase;
  locale: Locale;
  viewerRole: WorkspaceRole | string | null;
}) {
  const auth = useAuth();
  const toast = useToast();
  const copy = documentCentreCopy[locale];
  const api = useMemo(
    () => new BrowserApiClient(runtimeConfig.apiBaseUrl, auth.getAuthHeaders),
    [auth.getAuthHeaders],
  );
  const [documents, setDocuments] = useState<GeneratedDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const viewerMembershipId =
    auth.me?.memberships.find((membership) => membership.workspace_id === workspaceId)
      ?.membership_id ?? null;
  const isAssignedSponsor =
    viewerRole === "Sponsor" &&
    Boolean(viewerMembershipId) &&
    viewerMembershipId === programSponsorMembershipId;

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDocuments(await api.listDocuments(workspaceId, programId, useCase.id));
    } catch (nextError) {
      setError(problemMessage(nextError, copy.loadErrorTitle));
    } finally {
      setLoading(false);
    }
  }, [api, copy.loadErrorTitle, programId, useCase.id, workspaceId]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadDocuments();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadDocuments]);

  async function handleGenerate(type: DocumentType, format: DocumentFormat) {
    const key = `${type}:${format}`;
    setBusyKey(key);
    try {
      const next = await api.generateDocument(
        workspaceId,
        programId,
        useCase.id,
        { type, format, language: locale },
        crypto.randomUUID(),
      );
      setDocuments((current) => mergeDocument(current, next));
      toast.push({
        tone: "success",
        title: copy.toasts.generated,
        detail: labelForType(type, locale),
      });
    } catch (nextError) {
      toast.push({
        tone: "error",
        title: copy.loadErrorTitle,
        detail: problemMessage(nextError, copy.loadErrorTitle),
      });
    } finally {
      setBusyKey(null);
    }
  }

  async function handleApprove(documentId: string) {
    setBusyKey(`approve:${documentId}`);
    try {
      const next = await api.approveDocument(
        workspaceId,
        programId,
        useCase.id,
        documentId,
      );
      setDocuments((current) => mergeDocument(current, next));
      toast.push({ tone: "success", title: copy.toasts.approved });
    } catch (nextError) {
      toast.push({
        tone: "error",
        title: copy.loadErrorTitle,
        detail: problemMessage(nextError, copy.loadErrorTitle),
      });
    } finally {
      setBusyKey(null);
    }
  }

  async function handleDownload(versionId: string) {
    setBusyKey(`download:${versionId}`);
    try {
      const result = await api.downloadDocumentVersion(
        workspaceId,
        programId,
        useCase.id,
        versionId,
      );
      const url = URL.createObjectURL(result.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.push({
        tone: "success",
        title: copy.toasts.downloaded,
        detail: result.sha256 ?? copy.noData,
      });
    } catch (nextError) {
      toast.push({
        tone: "error",
        title: copy.loadErrorTitle,
        detail: problemMessage(nextError, copy.loadErrorTitle),
      });
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <Card>
      <CardHeader title={copy.title} description={copy.description} />
      {loading ? (
        <DocumentCentreLoading copy={copy} />
      ) : error ? (
        <EmptyState
          title={copy.loadErrorTitle}
          description={error}
          actionLabel={copy.retry}
          onAction={() => void loadDocuments()}
        />
      ) : !documents.length ? (
        <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
      ) : (
        <div className="space-y-6">
          {documents.map((document) => {
            const typeLabel = labelForType(document.type, locale);
            const currentVersion = document.current_version;
            const currentDownloadReason = currentVersionDownloadReason(
              viewerRole,
              currentVersion,
              locale,
            );
            const currentApproveReason =
              isAssignedSponsor && document.id ? currentApprovalReason(document, locale) : null;
            const currentSource = currentVersion
              ? formatVersionSource(currentVersion, locale)
              : formatEligibilitySource(document, locale, copy.noData);
            return (
              <section
                key={document.type}
                aria-labelledby={`document-centre-${document.type}`}
                className="rounded-2xl border border-[var(--studio-border)] p-4"
              >
                <div className="flex flex-col gap-3 border-b border-[var(--studio-border)] pb-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3
                        id={`document-centre-${document.type}`}
                        className="text-base font-semibold text-[var(--studio-foreground)]"
                      >
                        {typeLabel}
                      </h3>
                      <Badge tone={badgeTone(document.status)}>
                        {formatDocumentStatusLabel(document.status, locale)}
                      </Badge>
                    </div>
                    <p className="text-sm text-[var(--studio-muted)]">
                      {copy.versionsSource}: {currentSource}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-start gap-3">
                    <ActionButton
                      variant="secondary"
                      busy={busyKey !== null}
                      label={copy.generateMarkdown}
                      description={
                        document.eligibility.can_generate_markdown
                          ? null
                          : document.eligibility.markdown_reason
                      }
                      descriptionId={`document-${document.type}-markdown-reason`}
                      onClick={() => void handleGenerate(document.type, "markdown")}
                    />
                    <ActionButton
                      busy={busyKey !== null}
                      label={copy.generatePdf}
                      description={
                        document.eligibility.can_generate_pdf
                          ? null
                          : document.eligibility.pdf_reason
                      }
                      descriptionId={`document-${document.type}-pdf-reason`}
                      onClick={() => void handleGenerate(document.type, "pdf")}
                    />
                    {currentVersion ? (
                      <ActionButton
                        variant="ghost"
                        busy={busyKey !== null}
                        label={copy.download}
                        ariaLabel={copy.downloadCurrentAria(typeLabel)}
                        description={currentDownloadReason}
                        descriptionId={`document-${document.type}-download-reason`}
                        onClick={() => void handleDownload(currentVersion.id)}
                      />
                    ) : null}
                    {isAssignedSponsor &&
                    document.id &&
                    currentVersion &&
                    currentApproveReason !== copy.alreadyApproved ? (
                      <ActionButton
                        variant="secondary"
                        busy={busyKey !== null}
                        label={copy.approve}
                        ariaLabel={copy.approveCurrentAria(typeLabel)}
                        description={
                          currentApproveReason === copy.alreadyApproved
                            ? null
                            : currentApproveReason
                        }
                        descriptionId={`document-${document.type}-approve-reason`}
                        onClick={() => void handleApprove(document.id!)}
                      />
                    ) : null}
                  </div>
                </div>

                {currentVersion ? (
                  <div className="mt-4 grid gap-3 rounded-xl bg-[var(--studio-surface-subtle)] p-4 sm:grid-cols-2 xl:grid-cols-3">
                    <Info
                      label={copy.currentVersion}
                      value={`v${currentVersion.version_no} · ${formatDocumentFormatLabel(currentVersion.format, locale)}`}
                    />
                    <Info label={copy.versionsSource} value={currentSource} />
                    <Info
                      label={copy.createdAt}
                      value={formatDateTime(currentVersion.created_at, locale, copy.noData)}
                    />
                    <Info label={copy.createdBy} value={currentVersion.created_by_subject_id} />
                    <Info
                      label={copy.approval}
                      value={formatApprovalLabel(currentVersion, locale, copy.noData)}
                    />
                    <Info
                      label={copy.aiSections}
                      value={formatAiSectionsCount(
                        currentVersion.ai_assisted_sections.length,
                        locale,
                      )}
                    />
                  </div>
                ) : null}

                <div className="mt-4 space-y-3">
                  <h4 className="text-sm font-semibold text-[var(--studio-foreground)]">
                    {copy.versionHistory}
                  </h4>
                  {document.versions.length ? (
                    document.versions.map((version) => {
                      const derivedStatus = versionStatus(version);
                      const sponsorDownloadReason = currentVersionDownloadReason(
                        viewerRole,
                        version,
                        locale,
                      );
                      const versionSource = formatVersionSource(version, locale);
                      return (
                        <article
                          key={version.id}
                          className="rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] p-4"
                        >
                          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div className="space-y-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <p
                                  className={cn(
                                    "font-semibold text-[var(--studio-foreground)]",
                                    currentVersion?.id === version.id &&
                                      "text-[var(--studio-accent)]",
                                  )}
                                >
                                  v{version.version_no}
                                </p>
                                <Badge tone="info">
                                  {formatDocumentFormatLabel(version.format, locale)}
                                </Badge>
                                <Badge tone={badgeTone(derivedStatus)}>
                                  {formatDocumentStatusLabel(derivedStatus, locale)}
                                </Badge>
                              </div>
                              <p className="text-sm text-[var(--studio-muted)]">{versionSource}</p>
                            </div>
                            <ActionButton
                              variant="ghost"
                              busy={busyKey !== null}
                              label={copy.download}
                              ariaLabel={copy.downloadVersionAria(
                                typeLabel,
                                version.version_no,
                              )}
                              description={sponsorDownloadReason}
                              descriptionId={`document-${document.type}-version-${version.version_no}-download-reason`}
                              onClick={() => void handleDownload(version.id)}
                            />
                          </div>

                          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                            <Info
                              label={copy.createdAt}
                              value={formatDateTime(version.created_at, locale, copy.noData)}
                            />
                            <Info label={copy.createdBy} value={version.created_by_subject_id} />
                            <Info
                              label={copy.approval}
                              value={formatApprovalLabel(version, locale, copy.noData)}
                            />
                            <Info
                              label={copy.aiSections}
                              value={formatAiSectionsCount(
                                version.ai_assisted_sections.length,
                                locale,
                              )}
                            />
                            <Info
                              label={copy.metadataChanges}
                              value={
                                version.metadata_diff.length
                                  ? version.metadata_diff
                                      .map((code) => formatMetadataDiffLabel(code, locale))
                                      .join(" · ")
                                  : copy.noData
                              }
                            />
                            <Info label={copy.sha} value={version.sha256.slice(0, 16)} mono />
                          </div>
                        </article>
                      );
                    })
                  ) : (
                    <EmptyState
                      title={copy.emptyTitle}
                      description={copy.emptyDescription}
                    />
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </Card>
  );
}
