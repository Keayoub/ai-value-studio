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
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  ApiClientError,
  BrowserApiClient,
} from "@/features/api/browser-api-client";
import type {
  AssessmentEnvelope,
  JsonValue,
  KickstartProposal,
  KickstartSuggestion,
  UseCase,
  WizardAnswerResponse,
  WizardQuestion,
  WorkspaceMember,
  WorkspaceSummary,
} from "@/features/api/types";
import { useAuth } from "@/features/auth/auth-context";
import { getPublicRuntimeConfig } from "@/features/auth/runtime";
import { StepForm, ReviewPanel, DerivedPanel } from "@/features/studio/wizard/panels";
import { type Locale, wizardCopy } from "@/features/studio/wizard/copy";
import {
  formatTime,
  normalizeForServer,
  parseQuestionValue,
  splitListEntries,
  summarizeValue,
} from "@/features/studio/wizard/utils";
import { cn } from "@/lib/cn";

const runtimeConfig = getPublicRuntimeConfig(process.env);
const FIRST_EDITABLE_STEP = 1;
const LAST_STEP = 8;
const STORAGE_PREFIX = "avs.wizard.draft";
const SAVE_DEBOUNCE_MS = 700;

const KICKSTART_FIELD_CONFIG = [
  {
    id: "problem_statement",
    questionKey: "problem_statement",
    proposalKey: "problem_statement",
  },
  {
    id: "ai_solution",
    questionKey: "ai_task",
    proposalKey: "ai_solution",
  },
  {
    id: "kpi_proposals",
    questionKey: "primary_kpi",
    proposalKey: "kpi_proposals",
  },
  {
    id: "value_hypotheses",
    questionKey: "value_hypothesis",
    proposalKey: "value_hypotheses",
  },
  {
    id: "risks",
    questionKey: "risk_hypothesis",
    proposalKey: "risks",
  },
  {
    id: "missing_info",
    questionKey: "missing_knowledge",
    proposalKey: "missing_info",
  },
] as const;

type KickstartFieldId = (typeof KICKSTART_FIELD_CONFIG)[number]["id"];

type KickstartStatus =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; generatedAt: string }
  | { kind: "error"; message: string };

type KickstartFieldState =
  | { kind: "idle" }
  | { kind: "applying" }
  | { kind: "applied" }
  | { kind: "ignored" }
  | { kind: "error"; message: string };

type KickstartOverwriteDialogState = {
  fieldId: KickstartFieldId;
  nextValue: string;
  currentValue: string;
} | null;

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

function emptyKickstartFieldStates(): Record<KickstartFieldId, KickstartFieldState> {
  return Object.fromEntries(
    KICKSTART_FIELD_CONFIG.map((field) => [field.id, { kind: "idle" }]),
  ) as Record<KickstartFieldId, KickstartFieldState>;
}

function kickstartFieldLabel(fieldId: KickstartFieldId, labels: typeof wizardCopy.fr) {
  if (fieldId === "problem_statement") {
    return labels.kickstartProblemStatement;
  }
  if (fieldId === "ai_solution") {
    return labels.kickstartAiSolution;
  }
  if (fieldId === "kpi_proposals") {
    return labels.kickstartKpiProposals;
  }
  if (fieldId === "value_hypotheses") {
    return labels.kickstartValueHypotheses;
  }
  if (fieldId === "risks") {
    return labels.kickstartRisks;
  }
  return labels.kickstartMissingInfoTitle;
}

function kickstartEditorValue(field: (typeof KICKSTART_FIELD_CONFIG)[number], proposal: KickstartProposal) {
  const value = proposal[field.proposalKey];
  return Array.isArray(value) ? value.join("\n") : value;
}

function buildKickstartEditors(proposal: KickstartProposal): Record<KickstartFieldId, string> {
  return Object.fromEntries(
    KICKSTART_FIELD_CONFIG.map((field) => [field.id, kickstartEditorValue(field, proposal)]),
  ) as Record<KickstartFieldId, string>;
}

function serializeKickstartValue(fieldId: KickstartFieldId, value: string): string {
  if (fieldId === "kpi_proposals") {
    return splitListEntries(value).join("; ");
  }
  if (
    fieldId === "value_hypotheses" ||
    fieldId === "risks" ||
    fieldId === "missing_info"
  ) {
    return splitListEntries(value).join("\n");
  }
  return value.trim();
}

function stringifyQuestionValue(value: JsonValue, locale: Locale, labels: typeof wizardCopy.fr) {
  if (value === null) {
    return labels.kickstartNoAnswer;
  }
  if (typeof value === "string") {
    return value.trim() || labels.kickstartNoAnswer;
  }
  if (Array.isArray(value)) {
    return value
      .filter((entry): entry is string => typeof entry === "string")
      .join("\n");
  }
  return summarizeValue(value, locale, labels);
}

export function UseCaseWizard({
  workspaceId,
  programId,
  workspace,
  useCase,
  members,
  locale,
  viewerRole,
  onUseCaseChanged,
}: {
  workspaceId: string;
  programId: string;
  workspace: WorkspaceSummary | null;
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
  const [kickstartStatus, setKickstartStatus] = useState<KickstartStatus>({ kind: "idle" });
  const [kickstartSuggestion, setKickstartSuggestion] = useState<KickstartSuggestion | null>(null);
  const [kickstartEditors, setKickstartEditors] = useState<Record<KickstartFieldId, string>>(
    () => buildKickstartEditors({
      source: "ai_assisted",
      problem_statement: "",
      ai_solution: "",
      kpi_proposals: [],
      value_hypotheses: [],
      risks: [],
      missing_info: [],
    }),
  );
  const [kickstartFieldStates, setKickstartFieldStates] = useState<
    Record<KickstartFieldId, KickstartFieldState>
  >(() => emptyKickstartFieldStates());
  const [overwriteDialog, setOverwriteDialog] =
    useState<KickstartOverwriteDialogState>(null);
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

  useEffect(() => {
    setKickstartStatus({ kind: "idle" });
    setKickstartSuggestion(null);
    setKickstartEditors(
      buildKickstartEditors({
        source: "ai_assisted",
        problem_statement: "",
        ai_solution: "",
        kpi_proposals: [],
        value_hypotheses: [],
        risks: [],
        missing_info: [],
      }),
    );
    setKickstartFieldStates(emptyKickstartFieldStates());
    setOverwriteDialog(null);
  }, [envelope?.assessment.id]);

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

  const handleKickstartGenerate = useCallback(async () => {
    if (!envelope) {
      return;
    }
    setKickstartStatus({ kind: "loading" });
    setKickstartSuggestion(null);
    setKickstartFieldStates(emptyKickstartFieldStates());
    setOverwriteDialog(null);
    try {
      let assessmentId = envelope.assessment.id;
      if (Object.keys(pendingDrafts).length > 0) {
        await processPendingDrafts();
        const refreshed = await refreshAssessment(assessmentId);
        assessmentId = refreshed.assessment.id;
      }
      const suggestion = await api.generateAssessmentKickstart(
        workspaceId,
        programId,
        useCase.id,
        assessmentId,
      );
      setKickstartSuggestion(suggestion);
      setKickstartEditors(buildKickstartEditors(suggestion.proposal));
      setKickstartStatus({ kind: "ready", generatedAt: suggestion.generated_at });
    } catch (error) {
      setKickstartStatus({
        kind: "error",
        message: problemMessage(error, labels.networkError),
      });
    }
  }, [
    api,
    envelope,
    labels.networkError,
    pendingDrafts,
    processPendingDrafts,
    programId,
    refreshAssessment,
    useCase.id,
    workspaceId,
  ]);

  const handleKickstartEditorChange = useCallback(
    (fieldId: KickstartFieldId, value: string) => {
      setKickstartEditors((current) => ({ ...current, [fieldId]: value }));
      setKickstartFieldStates((current) => ({
        ...current,
        [fieldId]:
          current[fieldId]?.kind === "applying" ? current[fieldId] : { kind: "idle" },
      }));
    },
    [],
  );

  const applyKickstartField = useCallback(
    async (fieldId: KickstartFieldId, confirmOverwrite: boolean) => {
      if (!envelope) {
        return;
      }
      const field = KICKSTART_FIELD_CONFIG.find((entry) => entry.id === fieldId);
      if (!field) {
        return;
      }
      const question = findQuestion(envelope, field.questionKey);
      if (!question) {
        setKickstartFieldStates((current) => ({
          ...current,
          [fieldId]: { kind: "error", message: labels.loadingError },
        }));
        return;
      }
      const nextValue = serializeKickstartValue(fieldId, kickstartEditors[fieldId] ?? "");
      setKickstartFieldStates((current) => ({
        ...current,
        [fieldId]: { kind: "applying" },
      }));
      try {
        const answer = await api.upsertAssessmentAnswer(
          workspaceId,
          programId,
          useCase.id,
          envelope.assessment.id,
          field.questionKey,
          {
            value: nextValue,
            source: "ai_assisted",
            confirm_overwrite_ai_assisted: confirmOverwrite,
          },
        );
        const nextEnvelope = patchEnvelopeFromAnswer(envelope, answer);
        const nextDrafts = { ...pendingDrafts };
        delete nextDrafts[field.questionKey];
        setEnvelope(nextEnvelope);
        setPendingDrafts(nextDrafts);
        persistClientDraft(
          nextDrafts,
          currentStep,
          nextEnvelope.assessment.id,
          nextEnvelope,
        );
        setKickstartFieldStates((current) => ({
          ...current,
          [fieldId]: { kind: "applied" },
        }));
        setSaveState({ kind: "saved", at: new Date().toISOString() });
      } catch (error) {
        setKickstartFieldStates((current) => ({
          ...current,
          [fieldId]: {
            kind: "error",
            message: problemMessage(error, labels.networkError),
          },
        }));
      }
    },
    [
      api,
      currentStep,
      envelope,
      kickstartEditors,
      labels.loadingError,
      labels.networkError,
      pendingDrafts,
      persistClientDraft,
      programId,
      useCase.id,
      workspaceId,
    ],
  );

  const handleKickstartAccept = useCallback(
    (fieldId: KickstartFieldId) => {
      if (!envelope) {
        return;
      }
      const field = KICKSTART_FIELD_CONFIG.find((entry) => entry.id === fieldId);
      if (!field) {
        return;
      }
      const question = findQuestion(envelope, field.questionKey);
      if (!question) {
        return;
      }
      const nextValue = serializeKickstartValue(fieldId, kickstartEditors[fieldId] ?? "");
      const currentValue = stringifyQuestionValue(question.value, locale, labels);
      const hasCurrentAnswer =
        question.value !== null &&
        !(typeof question.value === "string" && question.value.trim() === "");
      const shouldConfirm =
        hasCurrentAnswer &&
        currentValue.trim() !== labels.kickstartNoAnswer &&
        currentValue.trim() !== nextValue.trim();
      if (shouldConfirm) {
        setOverwriteDialog({
          fieldId,
          nextValue,
          currentValue,
        });
        return;
      }
      void applyKickstartField(fieldId, false);
    },
    [applyKickstartField, envelope, kickstartEditors, labels, locale],
  );

  const handleKickstartIgnore = useCallback((fieldId: KickstartFieldId) => {
    setKickstartFieldStates((current) => ({
      ...current,
      [fieldId]: { kind: "ignored" },
    }));
  }, []);

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

  const canCreateAnotherVersion =
    envelope?.assessment.status === "Submitted" &&
    canCreateDraft &&
    (useCase.status === "ChangesRequested" || useCase.status === "Approved");
  const canGenerateKickstart =
    viewerRole === "Consultant" &&
    Boolean(envelope?.assessment.can_edit) &&
    Boolean(workspace?.ai_assistance_enabled) &&
    Boolean(workspace?.ai_assistance_available);
  const kickstartEligibilityMessage = !workspace?.ai_assistance_enabled
    ? labels.kickstartDisabledExplanation
    : !workspace.ai_assistance_available
      ? labels.kickstartUnavailableExplanation
      : viewerRole !== "Consultant"
        ? labels.kickstartConsultantOnlyExplanation
        : !envelope?.assessment.can_edit
          ? labels.kickstartDraftOnlyExplanation
          : labels.kickstartReadyDescription;

  const steps = useMemo(
    () => envelope?.template.steps.filter((step) => step.index > 0) ?? [],
    [envelope],
  );
  const mobileSteps = useMemo(() => {
    const activeStepEntry = steps.find((step) => step.index === currentStep);
    if (!activeStepEntry) {
      return steps;
    }
    return [activeStepEntry, ...steps.filter((step) => step.index !== currentStep)];
  }, [currentStep, steps]);
  const questionLabels = useMemo(
    () =>
      Object.fromEntries(
        steps.flatMap((step) =>
          step.questions.map((question) => [question.key, question.label] as const),
        ),
      ),
    [steps],
  );

  if (loading) {
    return (
      <Card>
        <CardHeader title={labels.loading} />
      </Card>
    );
  }

  function KickstartPanel({
    envelope,
    locale,
    labels,
    status,
    suggestion,
    editors,
    fieldStates,
    canGenerate,
    eligibilityMessage,
    onGenerate,
    onEditorChange,
    onAccept,
    onIgnore,
  }: {
    envelope: AssessmentEnvelope;
    locale: Locale;
    labels: typeof wizardCopy.fr;
    status: KickstartStatus;
    suggestion: KickstartSuggestion | null;
    editors: Record<KickstartFieldId, string>;
    fieldStates: Record<KickstartFieldId, KickstartFieldState>;
    canGenerate: boolean;
    eligibilityMessage: string;
    onGenerate: () => void;
    onEditorChange: (fieldId: KickstartFieldId, value: string) => void;
    onAccept: (fieldId: KickstartFieldId) => void;
    onIgnore: (fieldId: KickstartFieldId) => void;
  }) {
    const action = canGenerate ? (
      <Button onClick={onGenerate} disabled={status.kind === "loading"}>
        {status.kind === "loading" ? labels.kickstartGenerating : labels.kickstartGenerate}
      </Button>
    ) : (
      <Badge tone="warning">{labels.unavailableChip}</Badge>
    );

    return (
      <Card className="overflow-hidden">
        <CardHeader
          title={labels.kickstartTitle}
          description={labels.kickstartDescription}
          action={action}
        />
        <div className="space-y-4">
          <div className="rounded-2xl bg-[var(--studio-surface-subtle)] p-4">
            <p className="text-sm text-[var(--studio-muted)]">{eligibilityMessage}</p>
            {status.kind === "ready" ? (
              <p className="mt-2 text-sm font-medium text-[var(--studio-foreground)]">
                {labels.kickstartGeneratedAt} {formatTime(status.generatedAt, locale)}
              </p>
            ) : null}
          </div>

          {status.kind === "error" ? (
            <div
              role="alert"
              className="rounded-2xl border border-[var(--studio-danger)] bg-[var(--studio-danger-soft)] p-4"
            >
              <p className="text-sm text-[var(--studio-danger)]">{status.message}</p>
              {canGenerate ? (
                <div className="mt-3">
                  <Button variant="secondary" onClick={onGenerate}>
                    {labels.retry}
                  </Button>
                </div>
              ) : null}
            </div>
          ) : null}

          {suggestion ? (
            <div className="space-y-4">
              {KICKSTART_FIELD_CONFIG.map((field) => {
                const mappedQuestion = findQuestion(envelope, field.questionKey);
                const fieldState = fieldStates[field.id];
                const isIgnored = fieldState.kind === "ignored";
                const currentValue = mappedQuestion
                  ? stringifyQuestionValue(mappedQuestion.value, locale, labels)
                  : labels.noData;
                const editorValue = editors[field.id] ?? "";
                return (
                  <section
                    key={field.id}
                    className="rounded-2xl border border-[var(--studio-border)] p-4"
                  >
                    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold text-[var(--studio-foreground)]">
                          {kickstartFieldLabel(field.id, labels)}
                        </h3>
                        {field.id === "kpi_proposals" ? (
                          <p className="mt-1 text-sm text-[var(--studio-muted)]">
                            {labels.kickstartKpiHint}
                          </p>
                        ) : null}
                      </div>
                      {mappedQuestion?.source === "ai_assisted" ? (
                        <Badge tone="info">{labels.aiAssisted}</Badge>
                      ) : null}
                    </div>
                    {isIgnored ? (
                      <div className="rounded-2xl bg-[var(--studio-surface-subtle)] p-4">
                        <p className="text-sm text-[var(--studio-muted)]">
                          {labels.kickstartIgnored}
                        </p>
                        <div className="mt-3">
                          <Button
                            variant="secondary"
                            onClick={() => onEditorChange(field.id, editorValue)}
                          >
                            {labels.kickstartReviewAgain}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr),minmax(0,1fr)]">
                        <div className="space-y-2 rounded-2xl bg-[var(--studio-surface-subtle)] p-4">
                          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--studio-muted)]">
                            {labels.kickstartCurrentAnswer}
                          </p>
                          <p className="whitespace-pre-wrap text-sm text-[var(--studio-foreground)]">
                            {currentValue}
                          </p>
                        </div>
                        <div className="space-y-3 rounded-2xl border border-[var(--studio-border)] p-4">
                          <label
                            htmlFor={`kickstart-${field.id}`}
                            className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--studio-muted)]"
                          >
                            {labels.kickstartProposal}
                          </label>
                          <Textarea
                            id={`kickstart-${field.id}`}
                            value={editorValue}
                            onChange={(event) => onEditorChange(field.id, event.target.value)}
                            aria-label={`${kickstartFieldLabel(field.id, labels)} — ${labels.kickstartProposal}`}
                            disabled={fieldState.kind === "applying"}
                          />
                          <div className="flex flex-col gap-3 sm:flex-row">
                            <Button
                              onClick={() => onAccept(field.id)}
                              disabled={fieldState.kind === "applying" || !mappedQuestion}
                            >
                              {fieldState.kind === "applying"
                                ? labels.autosaveSaving
                                : labels.kickstartAccept}
                            </Button>
                            <Button
                              variant="secondary"
                              onClick={() => onIgnore(field.id)}
                              disabled={fieldState.kind === "applying"}
                            >
                              {labels.kickstartIgnore}
                            </Button>
                          </div>
                          {fieldState.kind === "applied" ? (
                            <p className="text-sm text-[var(--studio-success)]">
                              {labels.kickstartApplied}
                            </p>
                          ) : null}
                          {fieldState.kind === "error" ? (
                            <p role="alert" className="text-sm text-[var(--studio-danger)]">
                              {fieldState.message}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    )}
                  </section>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-[var(--studio-muted)]">{labels.kickstartNoProposal}</p>
          )}
        </div>
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

  const kickstartPanel = (
    <KickstartPanel
      envelope={envelope}
      locale={locale}
      labels={labels}
      status={kickstartStatus}
      suggestion={kickstartSuggestion}
      editors={kickstartEditors}
      fieldStates={kickstartFieldStates}
      canGenerate={canGenerateKickstart}
      eligibilityMessage={kickstartEligibilityMessage}
      onGenerate={() => void handleKickstartGenerate()}
      onEditorChange={handleKickstartEditorChange}
      onAccept={handleKickstartAccept}
      onIgnore={handleKickstartIgnore}
    />
  );

  return (
    <section className="flex flex-col gap-6">
      <Card className="order-1 xl:order-2">
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

        <div className="mt-6 xl:hidden">
          <div className="rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] p-4">
            <p className="text-sm font-semibold text-[var(--studio-brand)]">
              {labels.currentStep}
            </p>
            <ol
              className="mt-3 flex snap-x gap-3 overflow-x-auto pb-1"
              aria-label="Étapes de l’évaluation"
            >
              {mobileSteps.map((step) => {
                const validation = envelope.validation.find((entry) => entry.step === step.index);
                const stateLabel = !step.available
                  ? labels.unavailableChip
                  : step.index === currentStep
                    ? labels.stepCurrent
                    : validation?.is_valid
                      ? labels.stepComplete
                      : labels.stepPending;
                return (
                  <li key={step.index} className="min-w-[220px] snap-start">
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
          </div>
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[240px,minmax(0,1fr),minmax(0,280px)]">
          <aside className="hidden space-y-3 xl:block">
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
                role="alert"
                aria-labelledby="wizard-validation-summary-title"
                className="rounded-2xl border border-[var(--studio-danger)] bg-[var(--studio-danger-soft)] p-4"
              >
                <h3
                  id="wizard-validation-summary-title"
                  className="font-semibold text-[var(--studio-danger)]"
                >
                  {labels.validationSummaryTitle}
                </h3>
                <p className="mt-1 text-sm text-[var(--studio-danger)]">
                  {labels.validationSummaryDescription}
                </p>
                <ul className="mt-2 space-y-2 text-sm text-[var(--studio-danger)]">
                  {Object.entries(fieldErrors).map(([key, message]) => (
                    <li key={key}>
                      <a
                        href={`#wizard-${key}`}
                        className="underline underline-offset-2"
                        onClick={(event) => {
                          event.preventDefault();
                          fieldRefs.current[key]?.focus();
                        }}
                      >
                        {(questionLabels[key] ?? key)} — {message}
                      </a>
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
                onEditQuestion={(step, questionKey) => {
                  setDraftStep(step, envelope.assessment.id);
                  window.setTimeout(() => {
                    fieldRefs.current[questionKey]?.focus();
                  }, 0);
                }}
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

            <div className="sticky bottom-0 z-10 border-t border-[var(--studio-border)] bg-[var(--studio-surface)] py-4 shadow-[var(--shadow-sm)]">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm font-medium text-[var(--studio-muted)]">
                  {labels.progress} {currentStep} / {LAST_STEP}
                </p>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
                  {envelope.assessment.can_edit && currentStep > FIRST_EDITABLE_STEP ? (
                    <Button
                      className="min-h-[44px]"
                      variant="secondary"
                      onClick={() => setDraftStep(currentStep - 1, envelope.assessment.id)}
                    >
                      {labels.previous}
                    </Button>
                  ) : null}
                  {currentStep === LAST_STEP && envelope.assessment.can_edit ? (
                    <>
                      <Button
                        className="min-h-[44px]"
                        variant="secondary"
                        onClick={() => void processPendingDrafts()}
                      >
                        {labels.saveDraft}
                      </Button>
                      <div className="space-y-2">
                        <Button className="min-h-[44px]" variant="secondary" disabled aria-disabled="true">
                          {labels.requestInformation}
                        </Button>
                        <p className="max-w-sm text-xs text-[var(--studio-muted)]">
                          {labels.requestInformationUnavailable}
                        </p>
                      </div>
                    </>
                  ) : null}
                  {saveState.kind === "error" && envelope.assessment.can_edit ? (
                    <Button
                      className="min-h-[44px]"
                      variant="secondary"
                      onClick={() => void processPendingDrafts()}
                    >
                      {labels.retry}
                    </Button>
                  ) : null}
                  {canCreateAnotherVersion ? (
                    <Button
                      className="min-h-[44px]"
                      onClick={() =>
                        void handleCreateDraft(useCase.status === "Approved")
                      }
                    >
                      {labels.newDraft}
                    </Button>
                  ) : envelope.assessment.can_edit ? (
                    <Button className="min-h-[44px]" onClick={() => void handleContinue()}>
                      {currentStep === LAST_STEP ? labels.submit : labels.continue}
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>
          </div>

          <aside className="space-y-4">
            {currentStep === LAST_STEP ? null : (
              <DerivedPanel derived={envelope.derived} locale={locale} labels={labels} />
            )}
          </aside>
        </div>
      </Card>
      <div className="order-2 xl:order-1">{kickstartPanel}</div>
      <Dialog
        open={overwriteDialog !== null}
        title={labels.kickstartOverwriteTitle}
        description={labels.kickstartOverwriteDescription}
        onClose={() => setOverwriteDialog(null)}
        hideDefaultClose
      >
        {overwriteDialog ? (
          <div className="space-y-4">
            <div className="space-y-3 rounded-2xl bg-[var(--studio-surface-subtle)] p-4">
              <p className="text-sm font-semibold text-[var(--studio-foreground)]">
                {kickstartFieldLabel(overwriteDialog.fieldId, labels)}
              </p>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--studio-muted)]">
                    {labels.kickstartCurrentAnswer}
                  </p>
                  <p className="whitespace-pre-wrap text-sm text-[var(--studio-foreground)]">
                    {overwriteDialog.currentValue}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--studio-muted)]">
                    {labels.kickstartProposal}
                  </p>
                  <p className="whitespace-pre-wrap text-sm text-[var(--studio-foreground)]">
                    {overwriteDialog.nextValue}
                  </p>
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
              <Button variant="secondary" onClick={() => setOverwriteDialog(null)}>
                {labels.kickstartCancelOverwrite}
              </Button>
              <Button
                onClick={() => {
                  const pendingFieldId = overwriteDialog.fieldId;
                  setOverwriteDialog(null);
                  void applyKickstartField(pendingFieldId, true);
                }}
              >
                {labels.kickstartConfirmOverwrite}
              </Button>
            </div>
          </div>
        ) : null}
      </Dialog>
    </section>
  );
}
