"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import {
  ApiClientError,
  BrowserApiClient,
} from "@/features/api/browser-api-client";
import type {
  AssessmentEnvelope,
  JsonValue,
  UseCase,
  WizardAnswerResponse,
  WizardQuestion,
  WorkspaceMember,
} from "@/features/api/types";
import { useAuth } from "@/features/auth/auth-context";
import { getPublicRuntimeConfig } from "@/features/auth/runtime";
import { StepForm, ReviewPanel, DerivedPanel } from "@/features/studio/wizard/panels";
import { type Locale, wizardCopy } from "@/features/studio/wizard/copy";
import {
  formatTime,
  normalizeForServer,
  parseQuestionValue,
} from "@/features/studio/wizard/utils";
import { cn } from "@/lib/cn";

const runtimeConfig = getPublicRuntimeConfig(process.env);
const FIRST_EDITABLE_STEP = 1;
const LAST_STEP = 8;
const STORAGE_PREFIX = "avs.wizard.draft";
const SAVE_DEBOUNCE_MS = 700;

type SaveState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "saved"; at: string }
  | { kind: "error"; message: string };

type LocalDraftAnswer = {
  value: JsonValue;
  capturedForMembershipId: string | null;
};

type LocalWizardDraft = {
  assessmentId: string | null;
  step: number;
  answers: Record<string, LocalDraftAnswer>;
  envelopeSnapshot: AssessmentEnvelope | null;
};

function storageKeyFor(useCaseId: string) {
  return `${STORAGE_PREFIX}:${useCaseId}`;
}

function sanitizeStep(value: unknown): number {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return FIRST_EDITABLE_STEP;
  }
  return Math.min(LAST_STEP, Math.max(FIRST_EDITABLE_STEP, Math.trunc(numeric)));
}

function readDraft(useCaseId: string): LocalWizardDraft {
  if (typeof window === "undefined") {
    return {
      assessmentId: null,
      step: FIRST_EDITABLE_STEP,
      answers: {},
      envelopeSnapshot: null,
    };
  }
  const raw = window.localStorage.getItem(storageKeyFor(useCaseId));
  if (!raw) {
    return {
      assessmentId: null,
      step: FIRST_EDITABLE_STEP,
      answers: {},
      envelopeSnapshot: null,
    };
  }
  try {
    const parsed = JSON.parse(raw) as Partial<LocalWizardDraft>;
    return {
      assessmentId: typeof parsed.assessmentId === "string" ? parsed.assessmentId : null,
      step: sanitizeStep(parsed.step),
      answers:
        parsed.answers && typeof parsed.answers === "object"
          ? (parsed.answers as Record<string, LocalDraftAnswer>)
          : {},
      envelopeSnapshot:
        parsed.envelopeSnapshot && typeof parsed.envelopeSnapshot === "object"
          ? (parsed.envelopeSnapshot as AssessmentEnvelope)
          : null,
    };
  } catch {
    return {
      assessmentId: null,
      step: FIRST_EDITABLE_STEP,
      answers: {},
      envelopeSnapshot: null,
    };
  }
}

function writeDraft(useCaseId: string, draft: LocalWizardDraft) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(storageKeyFor(useCaseId), JSON.stringify(draft));
}

function deleteDraft(useCaseId: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(storageKeyFor(useCaseId));
}

function patchEnvelopeQuestion(
  envelope: AssessmentEnvelope,
  questionKey: string,
  nextValue: JsonValue,
  capturedForMembershipId: string | null,
) {
  return {
    ...envelope,
    template: {
      ...envelope.template,
      steps: envelope.template.steps.map((step) => ({
        ...step,
        questions: step.questions.map((question) =>
          question.key === questionKey
            ? {
                ...question,
                value: nextValue,
                captured_for_membership_id: capturedForMembershipId,
              }
            : question,
        ),
      })),
    },
  };
}

function patchEnvelopeFromAnswer(
  envelope: AssessmentEnvelope,
  answer: WizardAnswerResponse,
) {
  return {
    ...envelope,
    template: {
      ...envelope.template,
      steps: envelope.template.steps.map((step) => ({
        ...step,
        questions: step.questions.map((question) =>
          question.key === answer.question_key
            ? {
                ...question,
                value: answer.value,
                confidence: answer.confidence,
                evidence_text: answer.evidence_text,
                captured_for_membership_id: answer.captured_for_membership_id,
                source: answer.source,
                updated_at: answer.updated_at,
              }
            : question,
        ),
      })),
    },
  };
}

function findQuestion(envelope: AssessmentEnvelope | null, questionKey: string) {
  if (!envelope) {
    return null;
  }
  for (const step of envelope.template.steps) {
    const question = step.questions.find((entry) => entry.key === questionKey);
    if (question) {
      return question;
    }
  }
  return null;
}

function problemMessage(error: unknown, fallback: string) {
  if (error instanceof ApiClientError) {
    return error.problem.detail;
  }
  return error instanceof Error ? error.message : fallback;
}

function isNetworkError(error: unknown) {
  return error instanceof ApiClientError && error.problem.status === 0;
}

export function UseCaseWizard({
  workspaceId,
  programId,
  useCase,
  members,
  locale,
  viewerRole,
  onUseCaseChanged,
}: {
  workspaceId: string;
  programId: string;
  useCase: UseCase;
  members: WorkspaceMember[];
  locale: Locale;
  viewerRole: string | null;
  onUseCaseChanged?: () => Promise<void> | void;
}) {
  const auth = useAuth();
  const toast = useToast();
  const labels = wizardCopy[locale];
  const api = useMemo(
    () => new BrowserApiClient(runtimeConfig.apiBaseUrl, auth.getAuthHeaders),
    [auth.getAuthHeaders],
  );
  const canCreateDraft =
    viewerRole === "Consultant" || viewerRole === "WorkspaceAdmin";
  const canManageInterview = canCreateDraft;
  const [envelope, setEnvelope] = useState<AssessmentEnvelope | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(FIRST_EDITABLE_STEP);
  const [loading, setLoading] = useState(true);
  const [missingAssessment, setMissingAssessment] = useState(false);
  const [loadingError, setLoadingError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>({ kind: "idle" });
  const [pendingDrafts, setPendingDrafts] = useState<Record<string, LocalDraftAnswer>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [interviewDraft, setInterviewDraft] = useState({
    enabled: false,
    respondentMembershipId: "",
  });
  const [isOnline, setIsOnline] = useState(
    typeof navigator === "undefined" ? true : navigator.onLine,
  );
  const errorSummaryRef = useRef<HTMLDivElement>(null);
  const fieldRefs = useRef<Record<string, HTMLElement | null>>({});
  const pendingDraftSyncRef = useRef<Promise<void> | null>(null);

  const visibleStep = useMemo(
    () =>
      envelope?.template.steps.find((step) => step.index === currentStep) ?? null,
    [currentStep, envelope],
  );

  const respondentOptions = useMemo(
    () =>
      members.map((member) => ({
        id: member.membership_id,
        label: member.identity.display_name ?? member.membership_id,
      })),
    [members],
  );

  const persistClientDraft = useCallback(
    (
      nextDrafts: Record<string, LocalDraftAnswer>,
      nextStep: number,
      assessmentId: string | null,
      envelopeSnapshot: AssessmentEnvelope | null,
    ) => {
      writeDraft(useCase.id, {
        assessmentId,
        step: nextStep,
        answers: nextDrafts,
        envelopeSnapshot,
      });
    },
    [useCase.id],
  );

  const refreshAssessment = useCallback(
    async (assessmentId?: string) => {
      const response = assessmentId
        ? await api.getAssessment(workspaceId, programId, useCase.id, assessmentId)
        : await api.getCurrentAssessment(workspaceId, programId, useCase.id);
      const draft = readDraft(useCase.id);
      const nextStep =
        draft.assessmentId === response.assessment.id ? draft.step : currentStep;
      setEnvelope(response);
      setMissingAssessment(false);
      setLoadingError(null);
      setCurrentStep(sanitizeStep(nextStep));
      persistClientDraft(draft.answers, nextStep, response.assessment.id, response);
      return response;
    },
    [api, currentStep, persistClientDraft, programId, useCase.id, workspaceId],
  );

  const loadAssessment = useCallback(async () => {
    const draft = readDraft(useCase.id);
    setLoading(true);
    try {
      setPendingDrafts(draft.answers);
      setCurrentStep(draft.step);
      const response = await api.getCurrentAssessment(workspaceId, programId, useCase.id);
      setEnvelope(response);
      if (draft.assessmentId !== response.assessment.id && Object.keys(draft.answers).length > 0) {
        setPendingDrafts({});
        persistClientDraft({}, draft.step, response.assessment.id, response);
      } else {
        persistClientDraft(draft.answers, draft.step, response.assessment.id, response);
      }
      setMissingAssessment(false);
      setLoadingError(null);
      setSaveState({ kind: "idle" });
    } catch (error) {
      if (error instanceof ApiClientError && error.problem.status === 404) {
        setMissingAssessment(true);
        setEnvelope(null);
        setLoadingError(null);
      } else if (isNetworkError(error) && draft.envelopeSnapshot) {
        setEnvelope(draft.envelopeSnapshot);
        setMissingAssessment(false);
        setLoadingError(null);
        setFieldErrors({});
        setSaveState(
          Object.keys(draft.answers).length > 0
            ? { kind: "error", message: labels.networkError }
            : { kind: "idle" },
        );
      } else {
        setLoadingError(problemMessage(error, labels.loadingError));
      }
    } finally {
      setLoading(false);
    }
  }, [
    api,
    labels.loadingError,
    labels.networkError,
    persistClientDraft,
    programId,
    useCase.id,
    workspaceId,
  ]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadAssessment();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadAssessment]);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (!envelope) {
        setInterviewDraft({ enabled: false, respondentMembershipId: "" });
        return;
      }
      setInterviewDraft({
        enabled: envelope.assessment.interview_mode,
        respondentMembershipId: envelope.assessment.respondent_membership_id ?? "",
      });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [envelope]);

  const processPendingDrafts = useCallback(async () => {
    if (pendingDraftSyncRef.current) {
      return pendingDraftSyncRef.current;
    }
    const syncPromise = (async () => {
      if (!envelope || !isOnline || Object.keys(pendingDrafts).length === 0) {
        return;
      }
      setSaveState({ kind: "saving" });
      let nextEnvelope = envelope;
      const nextDrafts = { ...pendingDrafts };
      let shouldRefresh = false;
      let sentAny = false;

      for (const [questionKey, localDraft] of Object.entries(pendingDrafts)) {
        const question = findQuestion(nextEnvelope, questionKey);
        if (!question) {
          delete nextDrafts[questionKey];
          continue;
        }
        const normalizedValue = normalizeForServer(question, localDraft.value);
        if (normalizedValue === null) {
          continue;
        }
        try {
          const answer = await api.upsertAssessmentAnswer(
            workspaceId,
            programId,
            useCase.id,
            nextEnvelope.assessment.id,
            questionKey,
            {
              value: normalizedValue,
              captured_for_membership_id: localDraft.capturedForMembershipId,
            },
          );
          nextEnvelope = patchEnvelopeFromAnswer(nextEnvelope, answer);
          delete nextDrafts[questionKey];
          shouldRefresh = true;
          sentAny = true;
        } catch (error) {
          setSaveState({ kind: "error", message: problemMessage(error, labels.networkError) });
          setPendingDrafts(nextDrafts);
          persistClientDraft(nextDrafts, currentStep, nextEnvelope.assessment.id, nextEnvelope);
          return;
        }
      }

      setEnvelope(nextEnvelope);
      setPendingDrafts(nextDrafts);
      persistClientDraft(nextDrafts, currentStep, nextEnvelope.assessment.id, nextEnvelope);
      setSaveState(
        sentAny ? { kind: "saved", at: new Date().toISOString() } : { kind: "idle" },
      );
      if (shouldRefresh) {
        try {
          await refreshAssessment(nextEnvelope.assessment.id);
        } catch {
          // Keep the locally patched envelope and retry later if needed.
        }
      }
    })().finally(() => {
      pendingDraftSyncRef.current = null;
    });
    pendingDraftSyncRef.current = syncPromise;
    return syncPromise;
  }, [
    api,
    currentStep,
    envelope,
    isOnline,
    labels.networkError,
    pendingDrafts,
    persistClientDraft,
    programId,
    refreshAssessment,
    useCase.id,
    workspaceId,
  ]);

  useEffect(() => {
    if (!envelope || Object.keys(pendingDrafts).length === 0 || !isOnline) {
      return;
    }
    const timer = window.setTimeout(() => {
      void processPendingDrafts();
    }, SAVE_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [envelope, isOnline, pendingDrafts, processPendingDrafts]);

  const setDraftStep = useCallback(
    (nextStep: number, assessmentId: string | null) => {
      const sanitized = sanitizeStep(nextStep);
      setCurrentStep(sanitized);
      persistClientDraft(pendingDrafts, sanitized, assessmentId, envelope);
    },
    [envelope, pendingDrafts, persistClientDraft],
  );

  const handleCreateDraft = useCallback(async (forceNewVersion = false) => {
    try {
      const created = await api.createAssessment(workspaceId, programId, useCase.id, {
        force_new_version: forceNewVersion,
      });
      setEnvelope(created);
      setPendingDrafts({});
      setFieldErrors({});
      setSaveState({ kind: "idle" });
      setMissingAssessment(false);
      persistClientDraft({}, FIRST_EDITABLE_STEP, created.assessment.id, created);
      setCurrentStep(FIRST_EDITABLE_STEP);
      await onUseCaseChanged?.();
    } catch (error) {
      toast.push({
        tone: "error",
        title: labels.autosaveFailed,
        detail: problemMessage(error, labels.networkError),
      });
    }
  }, [
    api,
    labels.autosaveFailed,
    labels.networkError,
    onUseCaseChanged,
    persistClientDraft,
    programId,
    toast,
    useCase.id,
    workspaceId,
  ]);

  const handleInterviewSettingsChange = useCallback(
    async (interviewMode: boolean, respondentMembershipId: string | null) => {
      if (!envelope) {
        return;
      }
      try {
        if (
          respondentMembershipId !== envelope.assessment.respondent_membership_id &&
          envelope.assessment.respondent_membership_id &&
          !window.confirm(labels.confirmRespondent)
        ) {
          setInterviewDraft({
            enabled: envelope.assessment.interview_mode,
            respondentMembershipId: envelope.assessment.respondent_membership_id ?? "",
          });
          return;
        }
        const updated = await api.createAssessment(workspaceId, programId, useCase.id, {
          interview_mode: interviewMode,
          respondent_membership_id: respondentMembershipId,
        });
        setEnvelope(updated);
        persistClientDraft(pendingDrafts, currentStep, updated.assessment.id, updated);
      } catch (error) {
        setInterviewDraft({
          enabled: envelope.assessment.interview_mode,
          respondentMembershipId: envelope.assessment.respondent_membership_id ?? "",
        });
        toast.push({
          tone: "error",
          title: labels.autosaveFailed,
          detail: problemMessage(error, labels.networkError),
        });
      }
    },
    [
      api,
      currentStep,
      envelope,
      labels.confirmRespondent,
      labels.autosaveFailed,
      labels.networkError,
      pendingDrafts,
      persistClientDraft,
      programId,
      toast,
      useCase.id,
      workspaceId,
    ],
  );

  const handleQuestionChange = useCallback(
    (
      question: WizardQuestion,
      rawValue: string | boolean | number | string[],
    ) => {
      if (!envelope) {
        return;
      }
      const nextValue = parseQuestionValue(question, rawValue);
      const capturedForMembershipId = envelope.assessment.interview_mode
        ? envelope.assessment.respondent_membership_id
        : null;
      const nextDrafts = {
        ...pendingDrafts,
        [question.key]: {
          value: nextValue,
          capturedForMembershipId,
        },
      };
      const nextEnvelope = patchEnvelopeQuestion(
        envelope,
        question.key,
        nextValue,
        capturedForMembershipId,
      );
      setEnvelope((current) =>
        current
          ? patchEnvelopeQuestion(current, question.key, nextValue, capturedForMembershipId)
          : current,
      );
      setPendingDrafts(nextDrafts);
      setFieldErrors((current) => {
        const next = { ...current };
        delete next[question.key];
        return next;
      });
      persistClientDraft(nextDrafts, currentStep, envelope.assessment.id, nextEnvelope);
      setSaveState({ kind: "saving" });
    },
    [currentStep, envelope, pendingDrafts, persistClientDraft],
  );

  const handleContinue = useCallback(async () => {
    if (!envelope) {
      return;
    }
    if (currentStep >= LAST_STEP) {
      if (!envelope.assessment.can_submit) {
        return;
      }
      try {
        if (Object.keys(pendingDrafts).length > 0) {
          await processPendingDrafts();
          await refreshAssessment(envelope.assessment.id);
        }
        const submitted = await api.submitAssessment(
          workspaceId,
          programId,
          useCase.id,
          envelope.assessment.id,
        );
        setEnvelope(submitted.submitted);
        setPendingDrafts({});
        setFieldErrors({});
        deleteDraft(useCase.id);
        setSaveState({ kind: "saved", at: new Date().toISOString() });
        await onUseCaseChanged?.();
      } catch (error) {
        toast.push({
          tone: "error",
          title: labels.autosaveFailed,
          detail: problemMessage(error, labels.networkError),
        });
      }
      return;
    }
    try {
      if (Object.keys(pendingDrafts).length > 0) {
        await processPendingDrafts();
        await refreshAssessment(envelope.assessment.id);
      }
      const validation = await api.validateAssessmentStep(
        workspaceId,
        programId,
        useCase.id,
        envelope.assessment.id,
        currentStep,
      );
      setEnvelope((current) =>
        current
          ? {
              ...current,
              derived: validation.derived,
              validation: current.validation.map((entry) =>
                entry.step === validation.step ? validation : entry,
              ),
            }
          : current,
      );
      if (!validation.is_valid) {
        const nextErrors = Object.fromEntries(
          validation.errors.map((error) => [error.question_key, error.message]),
        );
        setFieldErrors(nextErrors);
        errorSummaryRef.current?.focus();
        const firstField = validation.errors[0]?.question_key;
        if (firstField) {
          fieldRefs.current[firstField]?.focus();
        }
        return;
      }
      const nextStep = Math.min(LAST_STEP, currentStep + 1);
      setFieldErrors({});
      setDraftStep(nextStep, envelope.assessment.id);
    } catch (error) {
      toast.push({
        tone: "error",
        title: labels.autosaveFailed,
        detail: problemMessage(error, labels.networkError),
      });
    }
  }, [
    api,
    currentStep,
    envelope,
    labels.autosaveFailed,
    labels.networkError,
    pendingDrafts,
    processPendingDrafts,
    programId,
    refreshAssessment,
    setDraftStep,
    toast,
    useCase.id,
    workspaceId,
    onUseCaseChanged,
  ]);

  const stepValidation = useMemo(
    () => envelope?.validation.find((entry) => entry.step === currentStep) ?? null,
    [currentStep, envelope],
  );

  const canCreateAnotherVersion =
    envelope?.assessment.status === "Submitted" &&
    canCreateDraft &&
    (useCase.status === "ChangesRequested" || useCase.status === "Approved");

  const steps = useMemo(
    () => envelope?.template.steps.filter((step) => step.index > 0) ?? [],
    [envelope],
  );

  if (loading) {
    return (
      <Card>
        <CardHeader title={labels.loading} />
      </Card>
    );
  }

  if (loadingError) {
    return (
      <Card>
        <CardHeader title={labels.loadingError} description={loadingError} />
        <Button variant="secondary" onClick={() => void loadAssessment()}>
          {labels.retry}
        </Button>
      </Card>
    );
  }

  if (missingAssessment && !canCreateDraft) {
    return (
      <EmptyState
        title={labels.unavailableTitle}
        description={labels.unavailableDescription}
      />
    );
  }

  if (missingAssessment) {
    return (
      <Card>
        <CardHeader
          title={labels.unavailableTitle}
          description={labels.unavailableDescription}
        />
        <Button onClick={() => void handleCreateDraft()}>{labels.createDraft}</Button>
      </Card>
    );
  }

  if (!envelope || !visibleStep) {
    return null;
  }

  return (
    <section className="space-y-6">
      <Card className="border-dashed">
        <CardHeader title={labels.kickstartTitle} description={labels.kickstartDescription} />
        <Badge tone="warning">{labels.unavailableChip}</Badge>
      </Card>

      <Card>
        <div className="flex flex-col gap-4 border-b border-[var(--studio-border)] pb-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-semibold text-[var(--studio-foreground)]">
                {visibleStep.title}
              </h2>
              {visibleStep.optional ? <Badge tone="info">{labels.optional}</Badge> : null}
              {!envelope.assessment.can_edit ? (
                <Badge tone="warning">{labels.readOnly}</Badge>
              ) : null}
            </div>
            <p className="text-sm text-[var(--studio-muted)]">{visibleStep.purpose}</p>
            <p className="text-sm text-[var(--studio-muted)]" role="status" aria-live="polite">
              {saveState.kind === "saving"
                ? labels.autosaveSaving
                : saveState.kind === "saved"
                  ? `${labels.autosaveSaved} ${formatTime(saveState.at, locale)}`
                  : saveState.kind === "error"
                    ? `${labels.autosaveFailed} ${saveState.message}`
                    : ""}
            </p>
          </div>
          <div className="rounded-2xl bg-[var(--studio-surface-subtle)] px-4 py-3 text-sm text-[var(--studio-muted)]">
            {labels.progress} {currentStep} / {LAST_STEP}
          </div>
        </div>

        {canManageInterview ? (
          <div className="mt-4 grid gap-4 rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] p-4 md:grid-cols-[minmax(0,1fr),minmax(0,1fr)]">
            <label className="flex items-center gap-3 text-sm font-medium text-[var(--studio-foreground)]">
              <input
                type="checkbox"
                checked={interviewDraft.enabled}
                onChange={(event) => {
                  const nextEnabled = event.target.checked;
                  setInterviewDraft((current) => ({ ...current, enabled: nextEnabled }));
                  if (!nextEnabled) {
                    void handleInterviewSettingsChange(false, null);
                    return;
                  }
                  if (interviewDraft.respondentMembershipId) {
                    void handleInterviewSettingsChange(
                      true,
                      interviewDraft.respondentMembershipId,
                    );
                  }
                }}
              />
              <span>{labels.interviewMode}</span>
            </label>
            <label className="space-y-2 text-sm font-medium text-[var(--studio-foreground)]">
              <span>{labels.respondent}</span>
              <Select
                value={interviewDraft.respondentMembershipId}
                disabled={!interviewDraft.enabled || !envelope.assessment.can_edit}
                onChange={(event) => {
                  const nextRespondentMembershipId = event.target.value;
                  setInterviewDraft((current) => ({
                    ...current,
                    respondentMembershipId: nextRespondentMembershipId,
                  }));
                  if (nextRespondentMembershipId) {
                    void handleInterviewSettingsChange(true, nextRespondentMembershipId);
                  }
                }}
              >
                <option value="">{labels.respondentMissing}</option>
                {respondentOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </label>
            <p className="text-sm text-[var(--studio-muted)] md:col-span-2">
              {labels.interviewHelp}
            </p>
            {envelope.assessment.interview_mode && envelope.assessment.respondent_membership_id ? (
              <p className="text-sm font-medium text-[var(--studio-foreground)] md:col-span-2">
                {labels.interviewBanner}{" "}
                {
                  respondentOptions.find(
                    (option) => option.id === envelope.assessment.respondent_membership_id,
                  )?.label
                }
                .
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="mt-6 grid gap-6 xl:grid-cols-[240px,minmax(0,1fr),minmax(0,280px)]">
          <aside className="space-y-3">
            <p className="text-sm font-semibold text-[var(--studio-brand)]">
              {labels.currentStep}
            </p>
            <ol className="space-y-2" aria-label="Étapes de l’évaluation">
              {steps.map((step) => {
                const validation = envelope.validation.find((entry) => entry.step === step.index);
                const stateLabel = !step.available
                  ? labels.unavailableChip
                  : step.index === currentStep
                    ? labels.stepCurrent
                    : validation?.is_valid
                      ? labels.stepComplete
                      : labels.stepPending;
                return (
                  <li key={step.index}>
                    <button
                      type="button"
                      className={cn(
                        "flex w-full items-start gap-3 rounded-2xl border px-3 py-3 text-start text-sm",
                        step.index === currentStep
                          ? "border-[var(--studio-brand)] bg-[var(--studio-surface-subtle)]"
                          : "border-[var(--studio-border)] bg-[var(--studio-surface)] hover:border-[var(--studio-border-strong)]",
                      )}
                      aria-current={step.index === currentStep ? "step" : undefined}
                      onClick={() => setDraftStep(step.index, envelope.assessment.id)}
                    >
                      <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--studio-brand)] text-xs font-semibold text-white">
                        {step.index}
                      </span>
                      <span className="space-y-1">
                        <span className="block font-medium text-[var(--studio-foreground)]">
                          {step.title}
                        </span>
                        <span className="block text-xs text-[var(--studio-muted)]">
                          {stateLabel}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </aside>

          <div className="space-y-6">
            {Object.keys(fieldErrors).length > 0 ? (
              <div
                ref={errorSummaryRef}
                tabIndex={-1}
                className="rounded-2xl border border-[var(--studio-danger)] bg-[var(--studio-danger-soft)] p-4"
              >
                <h3 className="font-semibold text-[var(--studio-danger)]">
                  {labels.missingInformation}
                </h3>
                <ul className="mt-2 space-y-2 text-sm text-[var(--studio-danger)]">
                  {Object.entries(fieldErrors).map(([key, message]) => (
                    <li key={key}>
                      <button
                        type="button"
                        className="underline underline-offset-2"
                        onClick={() => fieldRefs.current[key]?.focus()}
                      >
                        {message}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {currentStep === LAST_STEP ? (
              <ReviewPanel
                envelope={envelope}
                locale={locale}
                labels={labels}
                onEditStep={(step) => setDraftStep(step, envelope.assessment.id)}
                fieldRefs={fieldRefs}
                onQuestionChange={handleQuestionChange}
                fieldErrors={fieldErrors}
              />
            ) : (
              <StepForm
                step={visibleStep}
                labels={labels}
                fieldRefs={fieldRefs}
                fieldErrors={fieldErrors}
                onQuestionChange={handleQuestionChange}
              />
            )}

            <div className="flex flex-col gap-3 border-t border-[var(--studio-border)] pt-4 sm:flex-row sm:justify-between">
              {envelope.assessment.can_edit ? (
                <Button
                  variant="secondary"
                  disabled={currentStep <= FIRST_EDITABLE_STEP}
                  onClick={() => setDraftStep(currentStep - 1, envelope.assessment.id)}
                >
                  {labels.previous}
                </Button>
              ) : (
                <span />
              )}
              <div className="flex flex-col gap-3 sm:flex-row">
                {currentStep === LAST_STEP && envelope.assessment.can_edit ? (
                  <>
                    <Button variant="secondary" onClick={() => void processPendingDrafts()}>
                      {labels.saveDraft}
                    </Button>
                    <div className="space-y-2">
                      <Button variant="secondary" disabled aria-disabled="true">
                        {labels.requestInformation}
                      </Button>
                      <p className="max-w-sm text-xs text-[var(--studio-muted)]">
                        {labels.requestInformationUnavailable}
                      </p>
                    </div>
                  </>
                ) : null}
                {saveState.kind === "error" && envelope.assessment.can_edit ? (
                  <Button variant="secondary" onClick={() => void processPendingDrafts()}>
                    {labels.retry}
                  </Button>
                ) : null}
                {canCreateAnotherVersion ? (
                  <Button
                    onClick={() =>
                      void handleCreateDraft(useCase.status === "Approved")
                    }
                  >
                    {labels.newDraft}
                  </Button>
                ) : envelope.assessment.can_edit ? (
                  <Button onClick={() => void handleContinue()}>
                    {currentStep === LAST_STEP ? labels.submit : labels.continue}
                  </Button>
                ) : null}
              </div>
            </div>
          </div>

          <aside className="space-y-4">
            <DerivedPanel derived={envelope.derived} locale={locale} labels={labels} />
            {stepValidation && stepValidation.errors.length > 0 ? (
              <Card className="shadow-[var(--shadow-sm)]">
                <CardHeader
                  title={labels.missingInformation}
                  description={stepValidation.errors.map((error) => error.message).join(" · ")}
                />
              </Card>
            ) : null}
          </aside>
        </div>
      </Card>
    </section>
  );
}
