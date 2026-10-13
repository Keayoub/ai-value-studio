"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import {
  ApiClientError,
  BrowserApiClient,
} from "@/features/api/browser-api-client";
import type { ReviewInboxItem } from "@/features/api/types";
import { useAuth } from "@/features/auth/auth-context";
import { getPublicRuntimeConfig } from "@/features/auth/runtime";
import { formatUseCaseStatusLabel } from "@/features/studio/copy";

const runtimeConfig = getPublicRuntimeConfig(process.env);

const inboxCopy = {
  fr: {
    title: "À traiter",
    description:
      "Les éléments qui requièrent une décision sponsor ou une reprise consultant après demande de changements.",
    loading: "Chargement de la file de revue…",
    empty: "Aucun élément à traiter pour le moment.",
    retry: "Réessayer",
    loadError: "Impossible de charger la file de revue.",
    open: "Ouvrir la revue",
    assessmentVersion: "Version",
    submittedBy: "Soumis par",
  },
  en: {
    title: "Action queue",
    description:
      "Items that need a sponsor decision or a consultant follow-up after requested changes.",
    loading: "Loading review queue…",
    empty: "Nothing requires action right now.",
    retry: "Retry",
    loadError: "We could not load the review queue.",
    open: "Open review",
    assessmentVersion: "Version",
    submittedBy: "Submitted by",
  },
} as const;

type Locale = "fr" | "en";

function problemMessage(error: unknown, fallback: string) {
  if (error instanceof ApiClientError) {
    return error.problem.detail;
  }
  return error instanceof Error ? error.message : fallback;
}

function hrefForUseCase(
  workspaceId: string,
  programId: string,
  useCaseId: string,
) {
  return `/studio/use-case?workspaceId=${workspaceId}&programId=${programId}&useCaseId=${useCaseId}`;
}

export function ReviewInboxCard({
  workspaceId,
  locale,
}: {
  workspaceId: string;
  locale: Locale;
}) {
  const auth = useAuth();
  const copy = inboxCopy[locale];
  const api = useMemo(
    () => new BrowserApiClient(runtimeConfig.apiBaseUrl, auth.getAuthHeaders),
    [auth.getAuthHeaders],
  );

  const [items, setItems] = useState<ReviewInboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadInbox = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.listReviewInbox(workspaceId);
      setItems(response.items);
    } catch (nextError) {
      setError(problemMessage(nextError, copy.loadError));
    } finally {
      setLoading(false);
    }
  }, [api, copy.loadError, workspaceId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadInbox();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadInbox]);

  return (
    <Card>
      <CardHeader title={copy.title} description={copy.description} />
      {loading ? (
        <p className="text-sm text-[var(--studio-muted)]">{copy.loading}</p>
      ) : error ? (
        <div className="space-y-4">
          <p className="text-sm text-[var(--studio-danger)]">{error}</p>
          <Button variant="secondary" onClick={() => void loadInbox()}>
            {copy.retry}
          </Button>
        </div>
      ) : items.length === 0 ? (
        <EmptyState title={copy.title} description={copy.empty} />
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <article
              key={item.review_id}
              className="rounded-2xl border border-[var(--studio-border)] p-4"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-semibold text-[var(--studio-foreground)]">
                      {item.use_case_title}
                    </h3>
                    <Badge tone="info">{item.recommendation}</Badge>
                    <Badge tone="warning">
                      {formatUseCaseStatusLabel(locale, item.status)}
                    </Badge>
                  </div>
                  <p className="text-sm text-[var(--studio-muted)]">{item.program_name}</p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--studio-muted)]">
                    <span>
                      {copy.assessmentVersion} {item.assessment_version}
                    </span>
                    <span>
                      {copy.submittedBy} {item.submitted_by.display_name ?? item.submitted_by.subject_id}
                    </span>
                  </div>
                </div>
                <Link
                  className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-[var(--studio-border)] px-3 py-2 text-sm font-medium text-[var(--studio-accent)] transition hover:border-[var(--studio-accent)] hover:text-[var(--studio-accent-hover)]"
                  href={hrefForUseCase(workspaceId, item.program_id, item.use_case_id)}
                >
                  {copy.open}
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </Card>
  );
}
