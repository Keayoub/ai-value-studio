"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  ApiClientError,
  BrowserApiClient,
} from "@/features/api/browser-api-client";
import type {
  ReviewComment,
  ReviewDecision,
  ReviewRecommendation,
  ReviewState,
  UseCase,
} from "@/features/api/types";
import { useAuth } from "@/features/auth/auth-context";
import { getPublicRuntimeConfig } from "@/features/auth/runtime";
import { formatUseCaseStatusLabel } from "@/features/studio/copy";

const runtimeConfig = getPublicRuntimeConfig(process.env);

type Locale = "fr" | "en";

const reviewCopy = {
  fr: {
    title: "Revue sponsor",
    description:
      "Préparez la recommandation du consultant, relisez les cycles précédents et formalisez la décision sponsor pour la version en cours.",
    loading: "Chargement de la revue…",
    retry: "Réessayer",
    loadError: "Impossible de charger la revue.",
    noReviewTitle: "Aucune revue soumise",
    noReviewDescription:
      "La revue s’affiche après la soumission de la version actuelle de l’évaluation. Les cycles précédents restent consultables ci-dessous.",
    recommendation: "Recommandation consultant",
    summary: "Synthèse",
    risks: "Risques et points d’attention",
    submitReview: "Soumettre la revue",
    submitReviewHelp:
      "Cette étape transmet la recommandation du consultant pour la version actuellement soumise de l’évaluation.",
    recommendationPlaceholder: "Décrivez la logique, les garde-fous et les dépendances clés.",
    risksPlaceholder: "Un risque par ligne",
    comments: "Commentaires",
    commentsDescription:
      "Échanges partagés avec les membres affectés du programme. Chaque réponse reste liée au message d’origine.",
    addComment: "Ajouter un commentaire",
    reply: "Répondre",
    replyTo: "Réponse à",
    cancelReply: "Annuler la réponse",
    commentPlaceholder: "Saisissez un commentaire clair, contextualisé et actionnable.",
    noComments: "Aucun commentaire pour le moment.",
    decisionTitle: "Décision sponsor",
    decisionDescription:
      "Le sponsor statue sur la version en cours. Une version approuvée reste inchangée et toute évolution repart sur un nouveau brouillon.",
    decisionReason: "Motif ou commentaire de décision",
    decisionReasonPlaceholder:
      "Obligatoire pour demander des changements ou refuser. Optionnel si vous approuvez.",
    approve: "Approuver la recommandation",
    reject: "Rejeter",
    requestChanges: "Demander des changements",
    readOnly: "Lecture seule",
    timeline: "Historique",
    historyDescription:
      "Les cycles précédents restent consultables pour garder le contexte de décision.",
    assessmentVersion: "Version d’évaluation",
    currentAssessmentVersion: "Version en cours",
    submittedBy: "Soumis par",
    decidedBy: "Décidé par",
    submittedAt: "Soumis le",
    decidedAt: "Décidé le",
    noData: "Aucune donnée",
    draftReady:
      "Vous pouvez préparer une nouvelle version brouillon sans modifier la version déjà décidée.",
    confirmDecision:
      "Je confirme cette décision pour la version d’évaluation en cours et le périmètre présenté ci-dessus.",
    reviewCreated: "Revue soumise",
    commentCreated: "Commentaire enregistré",
    decisionSaved: "Décision enregistrée",
    previousCycles: "Cycles précédents",
  },
  en: {
    title: "Sponsor review",
    description:
      "Prepare the consultant recommendation, review earlier cycles, and record the sponsor decision for the current version.",
    loading: "Loading review…",
    retry: "Retry",
    loadError: "We could not load this review.",
    noReviewTitle: "No submitted review",
    noReviewDescription:
      "The review appears after the current assessment version is submitted. Earlier cycles remain available below for reference.",
    recommendation: "Consultant recommendation",
    summary: "Summary",
    risks: "Risks and watchpoints",
    submitReview: "Submit review",
    submitReviewHelp:
      "This sends the consultant recommendation for the assessment version that is currently submitted.",
    recommendationPlaceholder: "Describe the rationale, safeguards, and key dependencies.",
    risksPlaceholder: "One risk per line",
    comments: "Comments",
    commentsDescription:
      "Shared discussion with assigned program members. Replies stay attached to the parent comment.",
    addComment: "Add comment",
    reply: "Reply",
    replyTo: "Replying to",
    cancelReply: "Cancel reply",
    commentPlaceholder: "Enter a clear, contextual, actionable comment.",
    noComments: "No comments yet.",
    decisionTitle: "Sponsor decision",
    decisionDescription:
      "The sponsor decides on the current version. An approved version stays unchanged and any update starts from a new draft.",
    decisionReason: "Decision reason or comment",
    decisionReasonPlaceholder:
      "Required for reject or request changes. Optional when approving.",
    approve: "Approve recommendation",
    reject: "Reject",
    requestChanges: "Request changes",
    readOnly: "Read only",
    timeline: "Timeline",
    historyDescription: "Earlier cycles stay visible so the decision context is never lost.",
    assessmentVersion: "Assessment version",
    currentAssessmentVersion: "Current version",
    submittedBy: "Submitted by",
    decidedBy: "Decided by",
    submittedAt: "Submitted at",
    decidedAt: "Decided at",
    noData: "No data",
    draftReady: "You can prepare a new draft version without changing the decided version.",
    confirmDecision:
      "I confirm this decision for the current assessment version and the scope shown above.",
    reviewCreated: "Review submitted",
    commentCreated: "Comment saved",
    decisionSaved: "Decision saved",
    previousCycles: "Previous cycles",
  },
} as const;

function problemMessage(error: unknown, fallback: string) {
  if (error instanceof ApiClientError) {
    return error.problem.detail;
  }
  return error instanceof Error ? error.message : fallback;
}

function formatDateTime(value: string | null, locale: Locale) {
  if (!value) {
    return reviewCopy[locale].noData;
  }
  return new Intl.DateTimeFormat(locale === "fr" ? "fr-CA" : "en-CA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusTone(status: string) {
  if (status === "Approved") {
    return "success" as const;
  }
  if (status === "Rejected") {
    return "danger" as const;
  }
  if (status === "ChangesRequested") {
    return "warning" as const;
  }
  return "info" as const;
}

function displayName(name: string | null, fallback: string) {
  return name?.trim() || fallback;
}

function reviewVersionLabel(locale: Locale, version: number) {
  return `${reviewCopy[locale].assessmentVersion} ${version}`;
}

function buildCommentTree(comments: ReviewComment[]) {
  const byParent = new Map<string | null, ReviewComment[]>();
  for (const comment of comments) {
    const group = byParent.get(comment.parent_comment_id) ?? [];
    group.push(comment);
    byParent.set(comment.parent_comment_id, group);
  }
  return byParent;
}

function recommendationOptions(locale: Locale) {
  const map: Record<ReviewRecommendation, string> = {
    Go: "Go",
    Pilot: "Pilot",
    Defer: locale === "fr" ? "Différer" : "Defer",
    Reject: locale === "fr" ? "Rejeter" : "Reject",
  };
  return (["Go", "Pilot", "Defer", "Reject"] as ReviewRecommendation[]).map((value) => ({
    value,
    label: map[value],
  }));
}

function initialRecommendation(useCase: UseCase): ReviewRecommendation {
  const value = useCase.recommendation;
  if (value === "Go" || value === "Pilot" || value === "Defer" || value === "Reject") {
    return value;
  }
  return "Pilot";
}

export function UseCaseReviewPanel({
  workspaceId,
  programId,
  useCase,
  locale,
  onUseCaseChanged,
}: {
  workspaceId: string;
  programId: string;
  useCase: UseCase;
  locale: Locale;
  onUseCaseChanged?: () => Promise<void> | void;
}) {
  const auth = useAuth();
  const toast = useToast();
  const copy = reviewCopy[locale];
  const api = useMemo(
    () => new BrowserApiClient(runtimeConfig.apiBaseUrl, auth.getAuthHeaders),
    [auth.getAuthHeaders],
  );

  const [state, setState] = useState<ReviewState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recommendation, setRecommendation] = useState<ReviewRecommendation>(
    initialRecommendation(useCase),
  );
  const [summary, setSummary] = useState("");
  const [risksText, setRisksText] = useState("");
  const [commentBody, setCommentBody] = useState("");
  const [replyTo, setReplyTo] = useState<ReviewComment | null>(null);
  const [decisionReason, setDecisionReason] = useState("");
  const [decisionConfirmed, setDecisionConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const loadState = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const nextState = await api.getReviewState(workspaceId, programId, useCase.id);
      setState(nextState);
    } catch (nextError) {
      setError(problemMessage(nextError, copy.loadError));
    } finally {
      setLoading(false);
    }
  }, [api, copy.loadError, programId, useCase.id, workspaceId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadState();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadState]);

  const commentTree = useMemo(
    () => buildCommentTree(state?.comments ?? []),
    [state?.comments],
  );

  const handleCreateReview = useCallback(async () => {
    setSubmitting(true);
    try {
      const nextState = await api.createReview(workspaceId, programId, useCase.id, {
        recommendation,
        summary: summary.trim(),
        risks: risksText
          .split("\n")
          .map((entry) => entry.trim())
          .filter(Boolean),
      });
      setState(nextState);
      setSummary("");
      setRisksText("");
      toast.push({ tone: "success", title: copy.reviewCreated });
    } catch (nextError) {
      toast.push({
        tone: "error",
        title: copy.loadError,
        detail: problemMessage(nextError, copy.loadError),
      });
    } finally {
      setSubmitting(false);
    }
  }, [
    api,
    copy.loadError,
    copy.reviewCreated,
    programId,
    recommendation,
    risksText,
    summary,
    toast,
    useCase.id,
    workspaceId,
  ]);

  async function handleComment() {
    if (!commentBody.trim()) {
      return;
    }
    setSubmitting(true);
    try {
      const nextComment = await api.createReviewComment(workspaceId, programId, useCase.id, {
        body: commentBody.trim(),
        parent_comment_id: replyTo?.id ?? null,
      });
      setState((current) =>
        current
          ? {
              ...current,
              comments: [...current.comments, nextComment],
            }
          : current,
      );
      setCommentBody("");
      setReplyTo(null);
      toast.push({ tone: "success", title: copy.commentCreated });
    } catch (nextError) {
      toast.push({
        tone: "error",
        title: copy.loadError,
        detail: problemMessage(nextError, copy.loadError),
      });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDecision(decision: ReviewDecision) {
    const normalizedReason = decisionReason.trim();
    if (!state?.review) {
      return;
    }
    if (!decisionConfirmed) {
      return;
    }
    if (decision !== "Approved" && !normalizedReason) {
      return;
    }
    setSubmitting(true);
    try {
      const nextState = await api.decideReview(
        workspaceId,
        programId,
        useCase.id,
        state.review.id,
        decision,
        normalizedReason,
        crypto.randomUUID(),
      );
      setState(nextState);
      setDecisionReason("");
      setDecisionConfirmed(false);
      await onUseCaseChanged?.();
      toast.push({ tone: "success", title: copy.decisionSaved });
    } catch (nextError) {
      toast.push({
        tone: "error",
        title: copy.loadError,
        detail: problemMessage(nextError, copy.loadError),
      });
    } finally {
      setSubmitting(false);
    }
  }

  const currentAssessmentVersion = state?.review?.assessment_version ?? useCase.current_assessment_version;

  return (
    <Card>
      <CardHeader title={copy.title} description={copy.description} />
      {loading ? (
        <p className="text-sm text-[var(--studio-muted)]">{copy.loading}</p>
      ) : error ? (
        <div className="space-y-4">
          <p className="text-sm text-[var(--studio-danger)]">{error}</p>
          <Button variant="secondary" onClick={() => void loadState()}>
            {copy.retry}
          </Button>
        </div>
      ) : !state?.review ? (
        state?.can_submit_review ? (
          <div className="space-y-4">
            <div className="rounded-2xl bg-[var(--studio-surface-subtle)] p-4 text-sm text-[var(--studio-muted)]">
              {copy.submitReviewHelp}
            </div>
            {currentAssessmentVersion ? (
              <p className="text-sm font-medium text-[var(--studio-foreground)]">
                {copy.currentAssessmentVersion} {currentAssessmentVersion}
              </p>
            ) : null}
            <label className="space-y-2 text-sm">
              <span className="font-medium text-[var(--studio-foreground)]">
                {copy.recommendation}
              </span>
              <Select
                value={recommendation}
                onChange={(event) =>
                  setRecommendation(event.target.value as ReviewRecommendation)
                }
              >
                {recommendationOptions(locale).map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium text-[var(--studio-foreground)]">{copy.summary}</span>
              <Textarea
                value={summary}
                placeholder={copy.recommendationPlaceholder}
                onChange={(event) => setSummary(event.target.value)}
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium text-[var(--studio-foreground)]">{copy.risks}</span>
              <Textarea
                value={risksText}
                placeholder={copy.risksPlaceholder}
                onChange={(event) => setRisksText(event.target.value)}
              />
            </label>
            <Button
              onClick={() => void handleCreateReview()}
              disabled={submitting || !summary.trim()}
            >
              {copy.submitReview}
            </Button>
            {state.review_history.length > 0 ? (
              <ReviewHistorySection locale={locale} reviews={state.review_history} />
            ) : null}
          </div>
        ) : (
          <div className="space-y-4">
            <EmptyState
              title={copy.noReviewTitle}
              description={
                useCase.status === "Submitted"
                  ? copy.noReviewDescription
                  : `${copy.noReviewDescription} ${formatUseCaseStatusLabel(locale, useCase.status)}.`
              }
            />
            {state?.review_history.length ? (
              <ReviewHistorySection locale={locale} reviews={state.review_history} />
            ) : null}
          </div>
        )
      ) : (
        <div className="space-y-6">
          <section className="grid gap-4 lg:grid-cols-[1.1fr,0.9fr]">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={statusTone(state.review.status)}>
                  {formatUseCaseStatusLabel(locale, state.review.status)}
                </Badge>
                <Badge tone="default">
                  {copy.recommendation}: {state.review.recommendation}
                </Badge>
                {!state.can_comment ? <Badge tone="warning">{copy.readOnly}</Badge> : null}
              </div>
              <p className="text-sm font-medium text-[var(--studio-foreground)]">
                {reviewVersionLabel(locale, state.review.assessment_version)}
              </p>
              <div>
                <h3 className="text-sm font-semibold text-[var(--studio-muted)]">
                  {copy.summary}
                </h3>
                <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--studio-foreground)]">
                  {state.review.summary}
                </p>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[var(--studio-muted)]">
                  {copy.risks}
                </h3>
                {state.review.risks.length > 0 ? (
                  <ul className="mt-2 list-disc space-y-2 ps-5 text-sm text-[var(--studio-foreground)]">
                    {state.review.risks.map((risk, index) => (
                      <li key={`${index}:${risk}`}>{risk}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-sm text-[var(--studio-muted)]">{copy.noData}</p>
                )}
              </div>
              {state.review.decision_reason ? (
                <div className="rounded-2xl border border-[var(--studio-border)] p-4">
                  <h3 className="text-sm font-semibold text-[var(--studio-muted)]">
                    {copy.decisionReason}
                  </h3>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--studio-foreground)]">
                    {state.review.decision_reason}
                  </p>
                </div>
              ) : null}
            </div>
            <div className="rounded-2xl bg-[var(--studio-surface-subtle)] p-4">
              <h3 className="text-sm font-semibold text-[var(--studio-foreground)]">
                {copy.timeline}
              </h3>
              <dl className="mt-4 space-y-3 text-sm">
                <TimelineRow
                  label={copy.assessmentVersion}
                  value={String(state.review.assessment_version)}
                />
                <TimelineRow
                  label={copy.submittedBy}
                  value={displayName(
                    state.review.submitted_by.display_name,
                    state.review.submitted_by.subject_id,
                  )}
                />
                <TimelineRow
                  label={copy.submittedAt}
                  value={formatDateTime(state.review.submitted_at, locale)}
                />
                <TimelineRow
                  label={copy.decidedBy}
                  value={
                    state.review.decided_by
                      ? displayName(
                          state.review.decided_by.display_name,
                          state.review.decided_by.subject_id,
                        )
                      : copy.noData
                  }
                />
                <TimelineRow
                  label={copy.decidedAt}
                  value={formatDateTime(state.review.decided_at, locale)}
                />
              </dl>
            </div>
          </section>

          {state.review_history.length > 0 ? (
            <ReviewHistorySection locale={locale} reviews={state.review_history} />
          ) : null}

          <section className="space-y-4">
            <div>
              <h3 className="text-base font-semibold text-[var(--studio-foreground)]">
                {copy.comments}
              </h3>
              <p className="mt-1 text-sm text-[var(--studio-muted)]">{copy.commentsDescription}</p>
            </div>
            {state.comments.length === 0 ? (
              <EmptyState
                title={copy.comments}
                description={copy.noComments}
              />
            ) : (
              <CommentBranch
                commentsByParent={commentTree}
                locale={locale}
                onReply={state.can_comment ? setReplyTo : undefined}
                rootParentId={null}
                replyLabel={copy.reply}
              />
            )}
            {state.can_comment ? (
              <div className="space-y-3 rounded-2xl border border-[var(--studio-border)] p-4">
                {replyTo ? (
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[var(--studio-surface-subtle)] px-3 py-2 text-sm">
                    <span>
                      {copy.replyTo}{" "}
                      <strong>
                        {displayName(replyTo.author.display_name, replyTo.author.subject_id)}
                      </strong>
                    </span>
                    <Button variant="ghost" onClick={() => setReplyTo(null)}>
                      {copy.cancelReply}
                    </Button>
                  </div>
                ) : null}
                <Textarea
                  aria-label={copy.addComment}
                  value={commentBody}
                  placeholder={copy.commentPlaceholder}
                  onChange={(event) => setCommentBody(event.target.value)}
                />
                <Button
                  variant="secondary"
                  disabled={submitting || !commentBody.trim()}
                  onClick={() => void handleComment()}
                >
                  {copy.addComment}
                </Button>
              </div>
            ) : null}
          </section>

          {state.can_decide ? (
            <section className="space-y-4 rounded-2xl border border-[var(--studio-border)] p-4">
              <div>
                <h3 className="text-base font-semibold text-[var(--studio-foreground)]">
                  {copy.decisionTitle}
                </h3>
                <p className="mt-1 text-sm text-[var(--studio-muted)]">
                  {copy.decisionDescription}
                </p>
              </div>
              <label className="space-y-2 text-sm">
                <span className="font-medium text-[var(--studio-foreground)]">
                  {copy.decisionReason}
                </span>
                <Textarea
                  value={decisionReason}
                  placeholder={copy.decisionReasonPlaceholder}
                  onChange={(event) => setDecisionReason(event.target.value)}
                />
              </label>
              <label className="flex items-start gap-3 rounded-2xl bg-[var(--studio-surface-subtle)] px-4 py-3 text-sm text-[var(--studio-foreground)]">
                <input
                  type="checkbox"
                  checked={decisionConfirmed}
                  onChange={(event) => setDecisionConfirmed(event.target.checked)}
                />
                <span>
                  {copy.confirmDecision}
                  {state.review ? ` (${reviewVersionLabel(locale, state.review.assessment_version)}).` : ""}
                </span>
              </label>
              <div className="flex flex-wrap gap-3">
                <Button
                  disabled={submitting || !decisionConfirmed}
                  onClick={() => void handleDecision("Approved")}
                >
                  {copy.approve}
                </Button>
                <Button
                  variant="secondary"
                  disabled={submitting || !decisionConfirmed || !decisionReason.trim()}
                  onClick={() => void handleDecision("ChangesRequested")}
                >
                  {copy.requestChanges}
                </Button>
                <Button
                  variant="danger"
                  disabled={submitting || !decisionConfirmed || !decisionReason.trim()}
                  onClick={() => void handleDecision("Rejected")}
                >
                  {copy.reject}
                </Button>
              </div>
            </section>
          ) : null}

          {state.can_create_new_draft ? (
            <div className="rounded-2xl bg-[var(--studio-warning-soft)] px-4 py-3 text-sm text-[var(--studio-warning)]">
              {copy.draftReady}
            </div>
          ) : null}
        </div>
      )}
    </Card>
  );
}

function TimelineRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-medium text-[var(--studio-muted)]">{label}</dt>
      <dd className="mt-1 text-[var(--studio-foreground)]">{value}</dd>
    </div>
  );
}

function ReviewHistorySection({
  locale,
  reviews,
}: {
  locale: Locale;
  reviews: ReviewState["review_history"];
}) {
  const copy = reviewCopy[locale];

  return (
    <section className="space-y-4 rounded-2xl border border-[var(--studio-border)] p-4">
      <div>
        <h3 className="text-base font-semibold text-[var(--studio-foreground)]">
          {copy.previousCycles}
        </h3>
        <p className="mt-1 text-sm text-[var(--studio-muted)]">{copy.historyDescription}</p>
      </div>
      <div className="space-y-4">
        {reviews.map((review) => (
          <article
            key={review.id}
            className="space-y-4 rounded-2xl bg-[var(--studio-surface-subtle)] p-4"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={statusTone(review.status)}>
                {formatUseCaseStatusLabel(locale, review.status)}
              </Badge>
              <Badge tone="default">{reviewVersionLabel(locale, review.assessment_version)}</Badge>
              <Badge tone="warning">{copy.readOnly}</Badge>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-[var(--studio-muted)]">{copy.summary}</h4>
              <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--studio-foreground)]">
                {review.summary}
              </p>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-[var(--studio-muted)]">{copy.risks}</h4>
              {review.risks.length > 0 ? (
                <ul className="mt-2 list-disc space-y-2 ps-5 text-sm text-[var(--studio-foreground)]">
                  {review.risks.map((risk, index) => (
                    <li key={`${review.id}:${index}:${risk}`}>{risk}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-[var(--studio-muted)]">{copy.noData}</p>
              )}
            </div>
            {review.decision_reason ? (
              <div>
                <h4 className="text-sm font-semibold text-[var(--studio-muted)]">
                  {copy.decisionReason}
                </h4>
                <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--studio-foreground)]">
                  {review.decision_reason}
                </p>
              </div>
            ) : null}
            <dl className="grid gap-3 text-sm md:grid-cols-2">
              <TimelineRow
                label={copy.submittedBy}
                value={displayName(review.submitted_by.display_name, review.submitted_by.subject_id)}
              />
              <TimelineRow
                label={copy.submittedAt}
                value={formatDateTime(review.submitted_at, locale)}
              />
              <TimelineRow
                label={copy.decidedBy}
                value={
                  review.decided_by
                    ? displayName(review.decided_by.display_name, review.decided_by.subject_id)
                    : copy.noData
                }
              />
              <TimelineRow
                label={copy.decidedAt}
                value={formatDateTime(review.decided_at, locale)}
              />
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}

function CommentBranch({
  commentsByParent,
  locale,
  onReply,
  rootParentId,
  replyLabel,
}: {
  commentsByParent: Map<string | null, ReviewComment[]>;
  locale: Locale;
  onReply?: (comment: ReviewComment) => void;
  rootParentId: string | null;
  replyLabel: string;
}) {
  const comments = commentsByParent.get(rootParentId) ?? [];
  return (
    <div className="space-y-3">
      {comments.map((comment) => (
        <Fragment key={comment.id}>
          <div className="rounded-2xl border border-[var(--studio-border)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="space-y-1">
                <p className="text-sm font-semibold text-[var(--studio-foreground)]">
                  {displayName(comment.author.display_name, comment.author.subject_id)}
                </p>
                <p className="text-xs text-[var(--studio-muted)]">
                  {formatDateTime(comment.created_at, locale)}
                </p>
              </div>
              {onReply ? (
                <Button variant="ghost" onClick={() => onReply(comment)}>
                  {replyLabel}
                </Button>
              ) : null}
            </div>
            <p className="mt-3 whitespace-pre-wrap text-sm text-[var(--studio-foreground)]">
              {comment.body}
            </p>
          </div>
          {(commentsByParent.get(comment.id) ?? []).length > 0 ? (
            <div className="ms-4 border-s border-[var(--studio-border)] ps-4">
              <CommentBranch
                commentsByParent={commentsByParent}
                locale={locale}
                onReply={onReply}
                rootParentId={comment.id}
                replyLabel={replyLabel}
              />
            </div>
          ) : null}
        </Fragment>
      ))}
    </div>
  );
}
