"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

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
import { BrowserApiClient } from "@/features/api/browser-api-client";
import type {
  Program,
  ProgramStatus,
  UseCase,
  UseCaseStatus,
  WorkspaceMember,
  WorkspaceRole,
  WorkspaceSummary,
} from "@/features/api/types";
import { useAuth } from "@/features/auth/auth-context";
import {
  canAccessWorkspace,
  getViewerFlags,
  resolveMembershipLabel,
  resolveVisibleProgram,
  resolveVisibleUseCase,
  workspaceDisplayLanguage,
} from "@/features/auth/guards";
import { getPublicRuntimeConfig, isDesktopRuntime } from "@/features/auth/runtime";
import {
  formatProgramStatusLabel,
  formatUseCaseStatusLabel,
  formatWorkspaceRoleLabel,
  studioCopyFor,
} from "@/features/studio/copy";
import { localizeSeededDevFixtureName } from "@/features/studio/copy.dev";
import {
  Banner,
  UnauthenticatedContent,
} from "@/features/studio/mode-fragment";
import { DocumentCentre } from "@/features/studio/document-centre";
import { PortfolioMatrix } from "@/features/studio/portfolio-matrix";
import { ReviewInboxCard } from "@/features/studio/review-inbox";
import { LabeledField } from "@/features/studio/shared";
import { UseCaseReviewPanel } from "@/features/studio/use-case-review";
import { UseCaseScorecard } from "@/features/studio/use-case-scorecard";
import { UseCaseWizard } from "@/features/studio/use-case-wizard";
import { cn } from "@/lib/cn";

type StudioRoute = "home" | "workspace" | "program" | "use-case" | "portfolio" | "members";
type DesktopApiReachability = "reachable" | "unreachable";
type DesktopConnectivityKind = "checking" | "online" | "offline" | "unreachable";
type DesktopConnectivityState = {
  kind: DesktopConnectivityKind;
  healthOrigin: string | null;
};
type DecisionSurfaceKey = "review" | "scorecard" | "document-centre";
type DecisionSurfacePrerequisite = {
  key: DecisionSurfaceKey;
  title: string;
  detail: string;
};
type StudioLanguage = "fr" | "en";

const runtimeConfig = getPublicRuntimeConfig(process.env);
const DESKTOP_HEALTH_CHECK_TIMEOUT_MS = 3_000;
const DESKTOP_HEALTH_RETRY_DELAY_MS = 750;
const DESKTOP_HEALTH_MAX_ATTEMPTS = 2;

function hasSubmittedAssessmentSnapshot(useCase: UseCase) {
  return useCase.current_assessment_version !== null && useCase.submitted_at !== null;
}

function isPostSubmissionUseCase(useCase: UseCase) {
  return (
    useCase.status === "Submitted" ||
    useCase.status === "ChangesRequested" ||
    useCase.status === "Approved" ||
    useCase.status === "Rejected"
  );
}

function hasDecisionSurfaceData(useCase: UseCase) {
  return (
    hasSubmittedAssessmentSnapshot(useCase) ||
    useCase.score_version !== null ||
    useCase.approved_at !== null ||
    isPostSubmissionUseCase(useCase)
  );
}

function hasPreviousAssessmentCycle(useCase: UseCase) {
  return (useCase.current_assessment_version ?? 0) > 1;
}

function decisionSurfacePrerequisites(language: StudioLanguage): DecisionSurfacePrerequisite[] {
  if (language === "fr") {
    return [
      {
        key: "review",
        title: "Revue sponsor",
        detail:
          "Disponible après soumission de la version d’évaluation en cours pour lancer ou relire le cycle de revue.",
      },
      {
        key: "scorecard",
        title: "Scorecard de valeur et de priorité",
        detail:
          "Disponible dès qu’une version courante est soumise afin de recalculer le scorecard sur des données gelées.",
      },
      {
        key: "document-centre",
        title: "Centre documentaire",
        detail:
          "Disponible sur la version soumise; la génération reste pilotée par les prérequis réels d’évaluation, de scorecard et de revue sponsor.",
      },
    ];
  }

  return [
    {
      key: "review",
      title: "Sponsor review",
      detail:
        "Available after the current assessment version is submitted so the review cycle can start or earlier cycles can be revisited.",
    },
    {
      key: "scorecard",
      title: "Value and priority scorecard",
      detail:
        "Available once a current version is submitted so recalculation runs against a locked assessment snapshot.",
    },
    {
      key: "document-centre",
      title: "Document centre",
      detail:
        "Available on the submitted version; generation remains governed by the real assessment, scorecard, and sponsor review prerequisites.",
    },
  ];
}

export function StudioApp({ route }: { route: StudioRoute }) {
  const auth = useAuth();
  const toast = useToast();
  const searchParams = useSearchParams();
  const workspaceId = searchParams.get("workspaceId");
  const programId = searchParams.get("programId");
  const useCaseId = searchParams.get("useCaseId");
  const api = useMemo(
    () => new BrowserApiClient(runtimeConfig.apiBaseUrl, auth.getAuthHeaders),
    [auth.getAuthHeaders],
  );

  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [workspace, setWorkspace] = useState<WorkspaceSummary | null>(null);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [useCases, setUseCases] = useState<UseCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [primaryNavOpen, setPrimaryNavOpen] = useState(false);
  const [workspaceDialogOpen, setWorkspaceDialogOpen] = useState(false);
  const [workspaceForm, setWorkspaceForm] = useState({
    name: "",
    description: "",
    default_language: "fr-CA",
    confidentiality_policy: "internal-only",
  });
  const [programForm, setProgramForm] = useState({
    name: "",
    strategic_objective: "",
    sponsor_membership_id: "",
    consultant_membership_id: "",
  });
  const [useCaseForm, setUseCaseForm] = useState({
    title: "",
    department: "",
    owner_membership_id: "",
    recommendation: "",
  });
  const viewer = getViewerFlags(auth.me, workspaceId);
  const selectedProgram = resolveVisibleProgram(programs, programId);
  const selectedUseCase = resolveVisibleUseCase(useCases, useCaseId);
  const language = workspaceDisplayLanguage(workspace);
  const t = useMemo(() => studioCopyFor(language), [language]);
  const presentDevFixtureName = useCallback(
    (value: string | null | undefined) =>
      runtimeConfig.authMode === "dev" ? localizeSeededDevFixtureName(language, value) : value,
    [language],
  );
  const activeRoleLabel =
    auth.roleLabel &&
    ["Consultant", "Sponsor", "Contributor", "WorkspaceAdmin"].includes(auth.roleLabel)
      ? formatWorkspaceRoleLabel(language, auth.roleLabel as WorkspaceRole)
      : auth.roleLabel;
  const canCreateWorkspace =
    auth.me?.token_roles.includes("Consultant") || auth.me?.token_roles.includes("WorkspaceAdmin");
  const routeLinks = [
    { id: "home", href: hrefFor("home", {}), label: t.navigation.home },
    { id: "workspace", href: hrefFor("workspace", { workspaceId }), label: t.navigation.workspace },
    { id: "program", href: hrefFor("program", { workspaceId, programId }), label: t.navigation.program },
    {
      id: "use-case",
      href: hrefFor("use-case", { workspaceId, programId, useCaseId }),
      label: t.navigation.useCase,
    },
    { id: "portfolio", href: hrefFor("portfolio", { workspaceId, programId }), label: t.navigation.portfolio },
    { id: "members", href: hrefFor("members", { workspaceId }), label: t.navigation.members },
  ] satisfies Array<{ id: StudioRoute; href: string; label: string }>;
  const decisionSurfaceOpen = selectedUseCase ? hasDecisionSurfaceData(selectedUseCase) : false;
  const reviewSurfaceOpen = selectedUseCase
    ? decisionSurfaceOpen || hasPreviousAssessmentCycle(selectedUseCase)
    : false;
  const useCasePrerequisites = useMemo(
    () => decisionSurfacePrerequisites(language === "fr" ? "fr" : "en"),
    [language],
  );

  useEffect(() => {
    let active = true;
    async function load() {
      if (!auth.ready || auth.status !== "authenticated" || !auth.me) {
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const workspaceResult = await api.listWorkspaces();
        if (!active) {
          return;
        }
        setWorkspaces(workspaceResult.items);
        const selectedWorkspace = workspaceId
          ? workspaceResult.items.find((item) => item.id === workspaceId) ?? null
          : null;
        setWorkspace(selectedWorkspace);

        if (selectedWorkspace) {
          const [membersResult, programsResult] = await Promise.all([
            api.listWorkspaceMembers(selectedWorkspace.id).catch(() => ({ items: [], next_cursor: null })),
            api.listPrograms(selectedWorkspace.id),
          ]);
          if (!active) {
            return;
          }
          setMembers(membersResult.items);
          setPrograms(programsResult.items);

          if (programId) {
            const useCaseResult = await api.listUseCases(selectedWorkspace.id, programId).catch(() => ({
              items: [],
              next_cursor: null,
            }));
            if (!active) {
              return;
            }
            setUseCases(useCaseResult.items);
          } else {
            setUseCases([]);
          }
        } else {
          setMembers([]);
          setPrograms([]);
          setUseCases([]);
        }
      } catch (error) {
        toast.push({
          tone: "error",
          title: t.toasts.loadErrorTitle,
          detail: error instanceof Error ? error.message : t.toasts.loadErrorDetail,
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
  }, [api, auth.me, auth.ready, auth.status, programId, t, toast, workspaceId]);

  async function handleCreateWorkspace() {
    const created = await api.createWorkspace(workspaceForm);
    setWorkspaceDialogOpen(false);
    setWorkspaceForm({
      name: "",
      description: "",
      default_language: "fr-CA",
      confidentiality_policy: "internal-only",
    });
    await auth.refreshMe();
    toast.push({ tone: "success", title: t.toasts.workspaceCreated, detail: created.name });
    window.location.href = hrefFor("workspace", { workspaceId: created.id });
  }

  async function handleCreateProgram() {
    if (!workspaceId) {
      return;
    }
    const created = await api.createProgram(workspaceId, {
      name: programForm.name,
      strategic_objective: programForm.strategic_objective,
      sponsor_membership_id: programForm.sponsor_membership_id || null,
      consultant_membership_id: programForm.consultant_membership_id || null,
    });
    setProgramForm({ name: "", strategic_objective: "", sponsor_membership_id: "", consultant_membership_id: "" });
    toast.push({ tone: "success", title: t.toasts.programCreated, detail: created.name });
    window.location.href = hrefFor("program", { workspaceId, programId: created.id });
  }

  async function handleCreateUseCase() {
    if (!workspaceId || !programId) {
      return;
    }
    const created = await api.createUseCase(workspaceId, programId, {
      title: useCaseForm.title,
      department: useCaseForm.department,
      owner_membership_id: useCaseForm.owner_membership_id || null,
      recommendation: useCaseForm.recommendation,
    });
    setUseCaseForm({ title: "", department: "", owner_membership_id: "", recommendation: "" });
    toast.push({ tone: "success", title: t.toasts.useCaseCreated, detail: created.title });
    window.location.href = hrefFor("use-case", { workspaceId, programId, useCaseId: created.id });
  }

  async function handleProgramTransition(targetStatus: ProgramStatus) {
    if (!workspaceId || !programId) {
      return;
    }
    const updated = await api.transitionProgram(workspaceId, programId, targetStatus);
    setPrograms((current) => current.map((program) => (program.id === updated.id ? updated : program)));
    toast.push({
      tone: "success",
      title: t.toasts.programUpdated,
      detail: formatProgramStatusLabel(language, updated.status),
    });
  }

  async function handleUseCaseTransition(targetStatus: UseCaseStatus) {
    if (!workspaceId || !programId || !useCaseId) {
      return;
    }
    const updated = await api.transitionUseCase(workspaceId, programId, useCaseId, targetStatus);
    setUseCases((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    toast.push({
      tone: "success",
      title: t.toasts.useCaseUpdated,
      detail: formatUseCaseStatusLabel(language, updated.status),
    });
  }

  function handleUseCaseScoreSync(
    patch: Pick<UseCase, "priority_score" | "category" | "score_version" | "confidence_level">,
  ) {
    if (!useCaseId) {
      return;
    }
    setUseCases((current) =>
      current.map((item) =>
        item.id === useCaseId
          ? {
              ...item,
              ...patch,
            }
          : item,
      ),
    );
  }

  async function handleAssignProgramMember(membershipId: string) {
    if (!workspaceId || !programId || !membershipId) {
      return;
    }
    await api.assignProgramMember(workspaceId, programId, {
      membership_id: membershipId,
      assignment_role: "Contributor",
    });
    toast.push({ tone: "success", title: t.toasts.assignmentSaved });
  }

  async function handlePatchProgramSponsor(nextMembershipId: string) {
    if (!workspaceId || !programId) {
      return;
    }
    const updated = await api.updateProgram(workspaceId, programId, {
      sponsor_membership_id: nextMembershipId || null,
    });
    setPrograms((current) => current.map((program) => (program.id === updated.id ? updated : program)));
    toast.push({ tone: "success", title: t.toasts.sponsorUpdated });
  }

  async function handlePatchUseCaseOwner(nextMembershipId: string) {
    if (!workspaceId || !programId || !useCaseId) {
      return;
    }
    const updated = await api.updateUseCase(workspaceId, programId, useCaseId, {
      owner_membership_id: nextMembershipId || null,
    });
    setUseCases((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    toast.push({ tone: "success", title: t.toasts.ownerUpdated });
  }

  async function handleRefreshSelectedUseCase() {
    if (!workspaceId || !programId || !useCaseId) {
      return;
    }
    const refreshed = await api.getUseCase(workspaceId, programId, useCaseId);
    setUseCases((current) => current.map((item) => (item.id === refreshed.id ? refreshed : item)));
  }

  const content = (() => {
    if (auth.status !== "authenticated" || !auth.me) {
      return (
        <UnauthenticatedContent
          language={language}
          cardTitle={t.auth.cardTitle}
          error={auth.error}
        />
      );
    }

    if (route === "home") {
      return (
        <div className="grid gap-6 xl:grid-cols-[1.4fr,0.9fr]">
          <Card>
            <CardHeader
              title={t.home.workspaceTitle}
              description={t.home.workspaceDescription}
              action={
                canCreateWorkspace ? (
                  <Button onClick={() => setWorkspaceDialogOpen(true)}>
                    {t.home.createWorkspace}
                  </Button>
                ) : null
              }
            />
            <DataTable
              caption={t.home.workspaceCaption}
              headers={t.home.workspaceHeaders}
              rows={workspaces.map((item) => [
                <div key={item.id} className="space-y-1">
                  <p className="font-medium">{presentDevFixtureName(item.name)}</p>
                  <p className="text-xs text-[var(--studio-muted)]">{presentDevFixtureName(item.description) ?? t.common.none}</p>
                </div>,
                <Badge key={`${item.id}-role`}>{formatWorkspaceRoleLabel(language, item.my_role)}</Badge>,
                item.default_language,
                <Link
                  key={`${item.id}-link`}
                  className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-[var(--studio-border)] px-3 py-2 text-sm font-medium text-[var(--studio-accent)] transition hover:border-[var(--studio-accent)] hover:text-[var(--studio-accent-hover)]"
                  href={hrefFor("workspace", { workspaceId: item.id })}
                >
                  {t.common.open}
                </Link>,
              ])}
              empty={
                <EmptyState
                  title={t.home.noWorkspaceTitle}
                  description={t.home.noWorkspaceDescription}
                />
              }
            />
          </Card>
          <Card>
            <CardHeader
              title={t.home.activeIdentityTitle}
              description={t.home.activeIdentityDescription}
            />
            <dl className="grid gap-3 text-sm">
              <InfoRow
                label={t.home.activeIdentityName}
                value={presentDevFixtureName(auth.displayName) ?? t.common.none}
              />
              <InfoRow label={t.home.activeIdentityRole} value={activeRoleLabel ?? t.common.none} />
              <InfoRow label={t.home.activeIdentitySubject} value={auth.me.subject} />
              <InfoRow
                label={t.home.activeIdentityWorkspaceCount}
                value={String(auth.me.memberships.length)}
              />
            </dl>
          </Card>
        </div>
      );
    }

    if (!canAccessWorkspace(auth.me, workspaceId)) {
      return (
        <EmptyState
          title={t.workspace.inaccessibleTitle}
          description={t.workspace.inaccessibleDescription}
        />
      );
    }

    if (route === "workspace") {
      return (
        <div className="grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
          <Card>
            <CardHeader
              title={presentDevFixtureName(workspace?.name) ?? t.navigation.workspace}
              description={presentDevFixtureName(workspace?.description) ?? t.workspace.defaultDescription}
              action={
                viewer.canViewMembers ? (
                  <Link
                    href={hrefFor("members", { workspaceId })}
                    className="text-sm font-medium text-[var(--studio-accent)] hover:text-[var(--studio-accent-hover)]"
                  >
                    {t.navigation.viewMembers}
                  </Link>
                ) : null
              }
            />
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <InfoRow label={t.common.language} value={workspace?.default_language ?? t.common.none} />
              <InfoRow
                label={t.common.confidentiality}
                value={workspace?.confidentiality_policy ?? t.common.none}
              />
              <InfoRow
                label={t.common.role}
                value={workspace ? formatWorkspaceRoleLabel(language, workspace.my_role) : t.common.none}
              />
              <InfoRow label={t.common.status} value={workspace?.status ?? t.common.none} />
            </dl>
            <div className="mt-6">
              <DataTable
                caption={t.workspace.programCaption}
                headers={t.workspace.programHeaders}
                rows={programs.map((program) => [
                  <div key={program.id} className="space-y-1">
                    <p className="font-medium">{program.name}</p>
                    <p className="text-xs text-[var(--studio-muted)]">
                      {program.strategic_objective ?? t.workspace.objectiveFallback}
                    </p>
                  </div>,
                  <Badge key={`${program.id}-status`}>
                    {formatProgramStatusLabel(language, program.status)}
                  </Badge>,
                  resolveMembershipLabel(members, program.sponsor_membership_id),
                  <Link
                    key={`${program.id}-link`}
                    className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-[var(--studio-border)] px-3 py-2 text-sm font-medium text-[var(--studio-accent)] transition hover:border-[var(--studio-accent)] hover:text-[var(--studio-accent-hover)]"
                    href={hrefFor("program", { workspaceId, programId: program.id })}
                  >
                    {t.common.open}
                  </Link>,
                ])}
                empty={
                  <EmptyState
                    title={t.workspace.emptyProgramsTitle}
                    description={t.workspace.emptyProgramsDescription}
                  />
                }
              />
            </div>
          </Card>
          <div className="space-y-6">
            <Card>
              <CardHeader
                title={t.workspace.createProgramTitle}
                description={t.workspace.createProgramDescription}
              />
              <ProgramForm
                value={programForm}
                members={members}
                language={language}
                onChange={setProgramForm}
                onSubmit={() => void handleCreateProgram()}
                disabled={!viewer.canManagePrograms}
              />
            </Card>
            {workspaceId ? <ReviewInboxCard workspaceId={workspaceId} locale={language} /> : null}
          </div>
        </div>
      );
    }

    if (route === "members") {
      return (
        <Card>
          <CardHeader title={t.members.title} description={t.members.description} />
          {!viewer.canViewMembers ? (
            <EmptyState
              title={t.members.deniedTitle}
              description={t.members.deniedDescription}
            />
          ) : (
            <DataTable
              caption={t.members.caption}
              headers={t.members.headers}
              rows={members.map((member) => [
                member.identity.display_name ?? member.identity.email ?? t.common.none,
                <Badge key={`${member.membership_id}-role`}>
                  {formatWorkspaceRoleLabel(language, member.role)}
                </Badge>,
                member.status,
                <code key={`${member.membership_id}-id`} className="text-xs">
                  {member.membership_id}
                </code>,
              ])}
              empty={
                <EmptyState
                  title={t.members.emptyTitle}
                  description={t.members.emptyDescription}
                />
              }
            />
          )}
        </Card>
      );
    }

    if (route === "portfolio") {
      if (!workspaceId) {
        return (
          <EmptyState
            title={t.workspace.inaccessibleTitle}
            description={t.workspace.inaccessibleDescription}
          />
        );
      }
      return (
        <PortfolioMatrix
          workspaceId={workspaceId}
          visiblePrograms={programs}
          locale={language}
        />
      );
    }

    if (!selectedProgram) {
      return (
        <EmptyState
          title={t.program.notFoundTitle}
          description={t.program.notFoundDescription}
        />
      );
    }

    if (route === "program") {
      return (
        <div className="grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
          <div className="space-y-6">
            <Card>
              <CardHeader
                title={selectedProgram.name}
                description={selectedProgram.strategic_objective ?? t.program.defaultDescription}
              />
              <dl className="grid gap-3 text-sm sm:grid-cols-2">
                <InfoRow
                  label={t.common.status}
                  value={formatProgramStatusLabel(language, selectedProgram.status)}
                />
                <InfoRow
                  label={t.common.sponsor}
                  value={resolveMembershipLabel(members, selectedProgram.sponsor_membership_id)}
                />
                <InfoRow
                  label={t.common.consultant}
                  value={resolveMembershipLabel(members, selectedProgram.consultant_membership_id)}
                />
                <InfoRow
                  label={t.common.department}
                  value={selectedProgram.departments.join(", ") || t.common.none}
                />
              </dl>
              {viewer.canManagePrograms ? (
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  <LabeledField label={t.program.assignedSponsor}>
                    <Select
                      value={selectedProgram.sponsor_membership_id ?? ""}
                      onChange={(event) => void handlePatchProgramSponsor(event.target.value)}
                    >
                      <option value="">{t.common.noSponsor}</option>
                      {members.map((member) => (
                        <option key={member.membership_id} value={member.membership_id}>
                          {member.identity.display_name ?? member.identity.email ?? member.membership_id}
                        </option>
                      ))}
                    </Select>
                  </LabeledField>
                  <LabeledField label={t.program.statusTransition}>
                    <Select
                      aria-label={t.program.statusTransition}
                      defaultValue=""
                      onChange={(event) => {
                        if (event.target.value) {
                          void handleProgramTransition(event.target.value as ProgramStatus);
                        }
                      }}
                    >
                      <option value="">{t.program.statusPlaceholder}</option>
                      <option value="Discovery">{formatProgramStatusLabel(language, "Discovery")}</option>
                      <option value="Assessment">{formatProgramStatusLabel(language, "Assessment")}</option>
                      <option value="Prioritization">{formatProgramStatusLabel(language, "Prioritization")}</option>
                      <option value="Decision">{formatProgramStatusLabel(language, "Decision")}</option>
                      <option value="Closed">{formatProgramStatusLabel(language, "Closed")}</option>
                    </Select>
                  </LabeledField>
                </div>
              ) : null}
            </Card>
            <Card>
              <CardHeader
                title={t.program.visibleUseCasesTitle}
                description={t.program.visibleUseCasesDescription}
              />
              <DataTable
                caption={t.program.useCaseCaption}
                headers={t.program.useCaseHeaders}
                rows={useCases.map((item) => [
                  <div key={item.id} className="space-y-1">
                    <p className="font-medium">{item.title}</p>
                    <p className="text-xs text-[var(--studio-muted)]">
                      {item.department ?? t.program.departmentFallback}
                    </p>
                  </div>,
                  <Badge key={`${item.id}-status`}>
                    {formatUseCaseStatusLabel(language, item.status)}
                  </Badge>,
                  resolveMembershipLabel(members, item.owner_membership_id),
                  <Link
                    key={`${item.id}-link`}
                    className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-[var(--studio-border)] px-3 py-2 text-sm font-medium text-[var(--studio-accent)] transition hover:border-[var(--studio-accent)] hover:text-[var(--studio-accent-hover)]"
                    href={hrefFor("use-case", { workspaceId, programId, useCaseId: item.id })}
                  >
                    {t.common.open}
                  </Link>,
                ])}
                empty={
                  <EmptyState
                    title={t.program.emptyUseCasesTitle}
                    description={t.program.emptyUseCasesDescription}
                  />
                }
              />
            </Card>
          </div>
          <div className="space-y-6">
            <Card>
              <CardHeader
                title={t.program.createUseCaseTitle}
                description={t.program.createUseCaseDescription}
              />
              <UseCaseForm
                value={useCaseForm}
                members={members}
                language={language}
                onChange={setUseCaseForm}
                onSubmit={() => void handleCreateUseCase()}
                disabled={!viewer.canManageUseCases}
              />
            </Card>
            {viewer.canManagePrograms ? (
              <Card>
                <CardHeader
                  title={t.program.assignContributorTitle}
                  description={t.program.assignContributorDescription}
                />
                <LabeledField label={t.program.contributorToAssign}>
                  <Select defaultValue="" onChange={(event) => void handleAssignProgramMember(event.target.value)}>
                    <option value="">{t.common.choose}</option>
                    {members.map((member) => (
                      <option key={member.membership_id} value={member.membership_id}>
                        {member.identity.display_name ?? member.membership_id}
                      </option>
                    ))}
                  </Select>
                </LabeledField>
              </Card>
            ) : null}
          </div>
        </div>
      );
    }

    if (!selectedUseCase) {
      return (
        <EmptyState
          title={t.useCase.notFoundTitle}
          description={t.useCase.notFoundDescription}
        />
      );
    }

    if (route === "use-case") {
      const renderUseCaseDetails = () => (
        <>
          <div className="hidden xl:block">
            <CardHeader
              title={selectedUseCase.title}
              description={selectedUseCase.recommendation ?? t.useCase.defaultDescription}
            />
          </div>
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <InfoRow
              label={t.common.status}
              value={formatUseCaseStatusLabel(language, selectedUseCase.status)}
            />
            <InfoRow label={t.common.department} value={selectedUseCase.department ?? t.common.none} />
            <InfoRow
              label={t.common.owner}
              value={resolveMembershipLabel(members, selectedUseCase.owner_membership_id)}
            />
            <InfoRow label={t.common.category} value={selectedUseCase.category ?? t.common.none} />
            <InfoRow
              label={t.common.priorityScore}
              value={
                selectedUseCase.priority_score === null
                  ? t.common.none
                  : selectedUseCase.priority_score.toFixed(3)
              }
            />
            <InfoRow label={t.common.confidence} value={selectedUseCase.confidence_level ?? t.common.none} />
          </dl>
          {viewer.canManageUseCases ? (
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <LabeledField label={t.useCase.ownerLabel}>
                <Select
                  value={selectedUseCase.owner_membership_id ?? ""}
                  onChange={(event) => void handlePatchUseCaseOwner(event.target.value)}
                >
                  <option value="">{t.common.noOwner}</option>
                  {members.map((member) => (
                    <option key={member.membership_id} value={member.membership_id}>
                      {member.identity.display_name ?? member.membership_id}
                    </option>
                  ))}
                </Select>
              </LabeledField>
              {selectedUseCase.status === "Draft" ? (
                <LabeledField label={t.useCase.statusTransition}>
                  <Select
                    aria-label={t.useCase.statusTransition}
                    defaultValue=""
                    onChange={(event) => {
                      if (event.target.value) {
                        void handleUseCaseTransition(event.target.value as UseCaseStatus);
                      }
                    }}
                  >
                    <option value="">{t.common.choose}</option>
                    <option value="InProgress">
                      {formatUseCaseStatusLabel(language, "InProgress")}
                    </option>
                  </Select>
                </LabeledField>
              ) : null}
            </div>
          ) : null}
        </>
      );
      const renderUseCaseNavigation = () => (
        <Card>
          <CardHeader
            title={t.useCase.navigationTitle}
            description={t.useCase.navigationDescription}
          />
          <div className="space-y-3 text-sm">
            <NavLink href={hrefFor("workspace", { workspaceId })} label={t.navigation.backToWorkspace} />
            <NavLink href={hrefFor("program", { workspaceId, programId })} label={t.navigation.backToProgram} />
            {viewer.canViewMembers ? (
              <NavLink href={hrefFor("members", { workspaceId })} label={t.navigation.viewMembers} />
            ) : null}
          </div>
        </Card>
      );

      return (
        <div className="space-y-6">
          <Card className="xl:hidden">
            <CardHeader
              title={selectedUseCase.title}
              description={selectedUseCase.recommendation ?? t.useCase.defaultDescription}
            />
          </Card>
          {workspaceId && programId ? (
            <>
              <div className="flex flex-col gap-6">
                <div className="order-1 xl:order-2">
                  <UseCaseWizard
                    key={`wizard:${selectedUseCase.id}:${selectedUseCase.status}:${selectedUseCase.current_assessment_version ?? 0}`}
                    workspaceId={workspaceId}
                    programId={programId}
                    workspace={workspace}
                    useCase={selectedUseCase}
                    members={members}
                    locale={language}
                    viewerRole={viewer.role}
                    onUseCaseChanged={handleRefreshSelectedUseCase}
                  />
                </div>
                <div className="order-2 grid gap-6 xl:order-1 xl:grid-cols-[1.15fr,0.85fr]">
                  <Card>{renderUseCaseDetails()}</Card>
                  {renderUseCaseNavigation()}
                </div>
              </div>
              {reviewSurfaceOpen ? (
                <>
                  <UseCaseReviewPanel
                    key={`review:${selectedUseCase.id}:${selectedUseCase.status}:${selectedUseCase.current_assessment_version ?? 0}`}
                    workspaceId={workspaceId}
                    programId={programId}
                    useCase={selectedUseCase}
                    locale={language}
                    onUseCaseChanged={handleRefreshSelectedUseCase}
                  />
                  {decisionSurfaceOpen ? (
                    <>
                      <DocumentCentre
                        workspaceId={workspaceId}
                        programId={programId}
                        programSponsorMembershipId={selectedProgram?.sponsor_membership_id ?? null}
                        useCase={selectedUseCase}
                        locale={language}
                        viewerRole={viewer.role}
                      />
                      <UseCaseScorecard
                        workspaceId={workspaceId}
                        programId={programId}
                        useCase={selectedUseCase}
                        locale={language}
                        onUseCaseSync={handleUseCaseScoreSync}
                      />
                    </>
                  ) : null}
                  {!decisionSurfaceOpen ? (
                    <Card>
                      <CardHeader
                        title={
                          language === "fr"
                            ? "Surfaces de décision"
                            : "Decision surfaces"
                        }
                        description={
                          language === "fr"
                            ? "Les panneaux aval complets s’ouvrent après soumission de la version courante. Les prérequis ci-dessous reflètent le cycle réel."
                            : "Full downstream panels open after the current version is submitted. The prerequisites below reflect the real lifecycle."
                        }
                      />
                      <div className="divide-y divide-[var(--studio-border)] rounded-2xl border border-[var(--studio-border)]">
                        {useCasePrerequisites.map((item) => (
                          <div
                            key={item.key}
                            className="flex flex-col gap-3 px-4 py-4 md:flex-row md:items-start md:justify-between"
                          >
                            <div className="space-y-1">
                              <p className="font-medium text-[var(--studio-foreground)]">{item.title}</p>
                              <p className="max-w-3xl text-sm text-[var(--studio-muted)]">{item.detail}</p>
                            </div>
                            <div className="shrink-0 self-start">
                              <Badge tone="warning">
                                {language === "fr" ? "Pré-requis à satisfaire" : "Prerequisites pending"}
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </div>
                    </Card>
                  ) : null}
                </>
              ) : (
                <Card>
                  <CardHeader
                    title={
                      language === "fr"
                        ? "Surfaces de décision"
                        : "Decision surfaces"
                    }
                    description={
                      language === "fr"
                        ? "Les panneaux aval complets s’ouvrent après soumission de la version courante. Les prérequis ci-dessous reflètent le cycle réel."
                        : "Full downstream panels open after the current version is submitted. The prerequisites below reflect the real lifecycle."
                    }
                  />
                  <div className="divide-y divide-[var(--studio-border)] rounded-2xl border border-[var(--studio-border)]">
                    {useCasePrerequisites.map((item) => (
                      <div
                        key={item.key}
                        className="flex flex-col gap-3 px-4 py-4 md:flex-row md:items-start md:justify-between"
                      >
                        <div className="space-y-1">
                          <p className="font-medium text-[var(--studio-foreground)]">{item.title}</p>
                          <p className="max-w-3xl text-sm text-[var(--studio-muted)]">{item.detail}</p>
                        </div>
                        <div className="shrink-0 self-start">
                          <Badge tone="warning">
                            {language === "fr" ? "Pré-requis à satisfaire" : "Prerequisites pending"}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </>
          ) : null}
        </div>
      );
    }

    return null;
  })();

  return (
    <div className="min-h-screen bg-[var(--studio-background)]">
      <Banner language={language} />
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 lg:px-8">
        <header className="rounded-3xl border border-[var(--studio-border)] bg-[var(--studio-surface)] p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2">
              <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--studio-brand)]">
                {t.heroEyebrow}
              </p>
              <h1 className="text-3xl font-semibold text-[var(--studio-foreground)]">
                {t.heroTitle}
              </h1>
              <p className="max-w-3xl text-sm text-[var(--studio-muted)]">
                {t.heroDescription}
              </p>
            </div>
            <div className="flex flex-col items-start gap-3 rounded-2xl bg-[var(--studio-surface-subtle)] p-4 text-sm">
              <Badge tone={auth.status === "authenticated" ? "success" : "warning"}>
                {auth.status === "authenticated" ? t.sessionActive : t.sessionInactive}
              </Badge>
              <p className="font-medium text-[var(--studio-foreground)]">
                {presentDevFixtureName(auth.displayName) ?? t.noIdentity}
              </p>
              <p className="text-[var(--studio-muted)]">{activeRoleLabel ?? t.common.none}</p>
              {auth.status === "authenticated" ? (
                <Button variant="secondary" onClick={() => void auth.signOut()}>
                  {t.signOut}
                </Button>
              ) : null}
            </div>
          </div>
          <div className="mt-6 space-y-3">
            <div className="lg:hidden">
              <Button
                variant="secondary"
                aria-expanded={primaryNavOpen}
                aria-controls="studio-primary-navigation"
                onClick={() => setPrimaryNavOpen((current) => !current)}
              >
                {primaryNavOpen ? t.navigation.closeMenu : t.navigation.openMenu}
              </Button>
            </div>
            <nav
              id="studio-primary-navigation"
              aria-label={t.navigation.primary}
              className={cn(
                "rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] p-3 lg:block",
                primaryNavOpen ? "block" : "hidden",
              )}
            >
              <div className="grid gap-2 lg:grid-cols-6">
                {routeLinks.map((link) => (
                  <NavLink
                    key={link.id}
                    href={link.href}
                    label={link.label}
                    active={link.id === route}
                    onClick={() => setPrimaryNavOpen(false)}
                  />
                ))}
              </div>
            </nav>
          </div>
        </header>

        <DesktopConnectivityBanner language={language} />

        {loading ? <StudioLoadingState /> : content}
      </div>

      <Dialog
        open={workspaceDialogOpen}
        title={t.forms.createWorkspaceTitle}
        description={t.forms.createWorkspaceDescription}
        onClose={() => setWorkspaceDialogOpen(false)}
      >
        <div className="space-y-4">
          <LabeledField label={t.forms.workspaceName}>
            <Input
              value={workspaceForm.name}
              onChange={(event) => setWorkspaceForm((current) => ({ ...current, name: event.target.value }))}
            />
          </LabeledField>
          <LabeledField label={t.common.description}>
            <Textarea
              value={workspaceForm.description}
              onChange={(event) =>
                setWorkspaceForm((current) => ({ ...current, description: event.target.value }))
              }
            />
          </LabeledField>
          <div className="grid gap-4 sm:grid-cols-2">
            <LabeledField label={t.forms.defaultLanguage}>
              <Select
                value={workspaceForm.default_language}
                onChange={(event) =>
                  setWorkspaceForm((current) => ({ ...current, default_language: event.target.value }))
                }
              >
                <option value="fr-CA">fr-CA</option>
                <option value="en">en</option>
              </Select>
            </LabeledField>
            <LabeledField label={t.forms.confidentiality}>
              <Select
                value={workspaceForm.confidentiality_policy}
                onChange={(event) =>
                  setWorkspaceForm((current) => ({
                    ...current,
                    confidentiality_policy: event.target.value,
                  }))
                }
              >
                <option value="internal-only">internal-only</option>
                <option value="restricted">restricted</option>
                <option value="regulated">regulated</option>
              </Select>
            </LabeledField>
          </div>
          <div className="flex justify-end">
            <Button onClick={() => void handleCreateWorkspace()}>{t.forms.create}</Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}

function NavLink({
  href,
  label,
  active = false,
  onClick,
}: {
  href: string;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <Link
      className={cn(
        "inline-flex min-h-[44px] items-center justify-center rounded-lg border px-4 py-2 text-center text-sm font-medium transition focus-visible:ring-2 focus-visible:ring-[var(--studio-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--studio-surface)]",
        active
          ? "border-[var(--studio-brand)] bg-[var(--studio-surface)] text-[var(--studio-brand)] shadow-[var(--shadow-sm)]"
          : "border-[var(--studio-border)] bg-[var(--studio-surface)] text-[var(--studio-foreground)] hover:border-[var(--studio-brand)] hover:text-[var(--studio-brand)]",
      )}
      href={href}
      aria-current={active ? "page" : undefined}
      onClick={onClick}
    >
      {label}
    </Link>
  );
}

function StudioLoadingState() {
  return (
    <div
      aria-label={studioCopyFor("fr").loading.ariaLabel}
      className="grid gap-6 xl:grid-cols-[1.2fr,0.8fr]"
    >
      <Card>
        <Skeleton className="h-8 w-48" />
        <div className="mt-4 space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </Card>
      <Card>
        <Skeleton className="h-8 w-40" />
        <div className="mt-4 space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </Card>
    </div>
  );
}

function ProgramForm({
  value,
  members,
  language,
  disabled,
  onChange,
  onSubmit,
}: {
  value: {
    name: string;
    strategic_objective: string;
    sponsor_membership_id: string;
    consultant_membership_id: string;
  };
  members: WorkspaceMember[];
  language: "fr" | "en";
  disabled: boolean;
  onChange: React.Dispatch<
    React.SetStateAction<{
      name: string;
      strategic_objective: string;
      sponsor_membership_id: string;
      consultant_membership_id: string;
    }>
  >;
  onSubmit: () => void;
}) {
  const t = studioCopyFor(language);
  return (
    <div className="space-y-4">
      <LabeledField label={t.forms.programName}>
        <Input
          value={value.name}
          onChange={(event) => onChange((current) => ({ ...current, name: event.target.value }))}
        />
      </LabeledField>
      <LabeledField label={t.forms.strategicObjective}>
        <Textarea
          value={value.strategic_objective}
          onChange={(event) =>
            onChange((current) => ({ ...current, strategic_objective: event.target.value }))
          }
        />
      </LabeledField>
      <div className="grid gap-4 sm:grid-cols-2">
        <LabeledField label={t.common.sponsor}>
          <Select
            value={value.sponsor_membership_id}
            onChange={(event) =>
              onChange((current) => ({ ...current, sponsor_membership_id: event.target.value }))
            }
          >
            <option value="">{t.common.noSponsor}</option>
            {members.map((member) => (
              <option key={member.membership_id} value={member.membership_id}>
                {member.identity.display_name ?? member.membership_id}
              </option>
            ))}
          </Select>
        </LabeledField>
        <LabeledField label={t.forms.consultant}>
          <Select
            value={value.consultant_membership_id}
            onChange={(event) =>
              onChange((current) => ({
                ...current,
                consultant_membership_id: event.target.value,
              }))
            }
          >
            <option value="">{t.common.noConsultant}</option>
            {members.map((member) => (
              <option key={member.membership_id} value={member.membership_id}>
                {member.identity.display_name ?? member.membership_id}
              </option>
            ))}
          </Select>
        </LabeledField>
      </div>
      <Button className="w-full" disabled={disabled || !value.name.trim()} onClick={onSubmit}>
        {t.forms.createProgram}
      </Button>
    </div>
  );
}

function UseCaseForm({
  value,
  members,
  language,
  disabled,
  onChange,
  onSubmit,
}: {
  value: {
    title: string;
    department: string;
    owner_membership_id: string;
    recommendation: string;
  };
  members: WorkspaceMember[];
  language: "fr" | "en";
  disabled: boolean;
  onChange: React.Dispatch<
    React.SetStateAction<{
      title: string;
      department: string;
      owner_membership_id: string;
      recommendation: string;
    }>
  >;
  onSubmit: () => void;
}) {
  const t = studioCopyFor(language);
  return (
    <div className="space-y-4">
      <LabeledField label={t.forms.useCaseTitle}>
        <Input
          value={value.title}
          onChange={(event) => onChange((current) => ({ ...current, title: event.target.value }))}
        />
      </LabeledField>
      <LabeledField label={t.common.department}>
        <Input
          value={value.department}
          onChange={(event) =>
            onChange((current) => ({ ...current, department: event.target.value }))
          }
        />
      </LabeledField>
      <LabeledField label={t.forms.owner}>
        <Select
          value={value.owner_membership_id}
          onChange={(event) =>
            onChange((current) => ({ ...current, owner_membership_id: event.target.value }))
          }
        >
          <option value="">{t.common.noOwner}</option>
          {members.map((member) => (
            <option key={member.membership_id} value={member.membership_id}>
              {member.identity.display_name ?? member.membership_id}
            </option>
          ))}
        </Select>
      </LabeledField>
      <LabeledField label={t.common.recommendation}>
        <Textarea
          value={value.recommendation}
          onChange={(event) =>
            onChange((current) => ({ ...current, recommendation: event.target.value }))
          }
        />
      </LabeledField>
      <Button className="w-full" disabled={disabled || !value.title.trim()} onClick={onSubmit}>
        {t.forms.createUseCase}
      </Button>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-[var(--studio-surface-subtle)] px-3 py-2">
      <dt className="text-xs uppercase tracking-wide text-[var(--studio-muted)]">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-[var(--studio-foreground)]">{value}</dd>
    </div>
  );
}

function hrefFor(
  route: StudioRoute,
  params: {
    workspaceId?: string | null;
    programId?: string | null;
    useCaseId?: string | null;
  },
) {
  const base =
    route === "home"
      ? "/studio"
      : route === "workspace"
        ? "/studio/workspace"
        : route === "program"
          ? "/studio/program"
          : route === "use-case"
            ? "/studio/use-case"
            : route === "portfolio"
              ? "/studio/portfolio"
              : "/studio/admin/members";
  const query = new URLSearchParams();
  if (params.workspaceId) {
    query.set("workspaceId", params.workspaceId);
  }
  if (params.programId) {
    query.set("programId", params.programId);
  }
  if (params.useCaseId) {
    query.set("useCaseId", params.useCaseId);
  }
  return query.size ? `${base}?${query.toString()}` : base;
}

export function StudioRoutePage({ route }: { route: StudioRoute }) {
  return (
    <Suspense fallback={<StudioLoadingState />}>
      <StudioApp route={route} />
    </Suspense>
  );
}

export function deriveDesktopHealthEndpoint(apiBaseUrl: string): string | null {
  try {
    return new URL("/health", new URL(apiBaseUrl).origin).toString();
  } catch {
    return null;
  }
}

export function classifyDesktopApiReachability(status: number): DesktopApiReachability {
  if ((status >= 200 && status < 300) || status === 401) {
    return "reachable";
  }
  return "unreachable";
}

export function resolveDesktopConnectivityState({
  isOnline,
  reachability,
  healthOrigin,
}: {
  isOnline: boolean;
  reachability: DesktopApiReachability;
  healthOrigin: string | null;
}): DesktopConnectivityState {
  if (!isOnline) {
    return { kind: "offline", healthOrigin };
  }
  return {
    kind: reachability === "reachable" ? "online" : "unreachable",
    healthOrigin,
  };
}

function waitForDesktopHealthRetry(signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      signal.removeEventListener("abort", handleAbort);
      resolve();
    }, DESKTOP_HEALTH_RETRY_DELAY_MS);

    const handleAbort = () => {
      window.clearTimeout(timeoutId);
      signal.removeEventListener("abort", handleAbort);
      reject(new DOMException("Desktop health retry aborted.", "AbortError"));
    };

    signal.addEventListener("abort", handleAbort, { once: true });
  });
}

async function probeDesktopApiReachability(
  healthEndpoint: string,
  signal: AbortSignal,
): Promise<DesktopApiReachability> {
  for (let attempt = 1; attempt <= DESKTOP_HEALTH_MAX_ATTEMPTS; attempt += 1) {
    const attemptController = new AbortController();
    const timeoutId = window.setTimeout(() => attemptController.abort(), DESKTOP_HEALTH_CHECK_TIMEOUT_MS);
    const forwardAbort = () => attemptController.abort();

    signal.addEventListener("abort", forwardAbort, { once: true });
    try {
      const response = await fetch(healthEndpoint, {
        method: "GET",
        cache: "no-store",
        signal: attemptController.signal,
      });
      return classifyDesktopApiReachability(response.status);
    } catch (error) {
      if (signal.aborted) {
        throw error;
      }
      if (attempt === DESKTOP_HEALTH_MAX_ATTEMPTS) {
        return "unreachable";
      }
      await waitForDesktopHealthRetry(signal);
    } finally {
      window.clearTimeout(timeoutId);
      signal.removeEventListener("abort", forwardAbort);
    }
  }

  return "unreachable";
}

function DesktopConnectivityBanner({ language }: { language: "fr" | "en" }) {
  const healthEndpoint = useMemo(
    () => deriveDesktopHealthEndpoint(runtimeConfig.apiBaseUrl),
    [],
  );
  const healthOrigin = useMemo(() => {
    if (!healthEndpoint) {
      return null;
    }
    return new URL(healthEndpoint).origin;
  }, [healthEndpoint]);
  const [connectivity, setConnectivity] = useState<DesktopConnectivityState>(() =>
    resolveDesktopConnectivityState({
      isOnline: typeof navigator === "undefined" ? true : navigator.onLine,
      reachability: "reachable",
      healthOrigin,
    }),
  );
  const checkControllerRef = useRef<AbortController | null>(null);

  const refreshConnectivity = useCallback(
    async () => {
      if (!isDesktopRuntime()) {
        return;
      }

      const online = typeof navigator === "undefined" ? true : navigator.onLine;
      if (!online) {
        checkControllerRef.current?.abort();
        setConnectivity({ kind: "offline", healthOrigin });
        return;
      }
      if (!healthEndpoint) {
        setConnectivity({ kind: "unreachable", healthOrigin });
        return;
      }

      checkControllerRef.current?.abort();
      const controller = new AbortController();
      checkControllerRef.current = controller;
      setConnectivity({ kind: "checking", healthOrigin });

      try {
        const reachability = await probeDesktopApiReachability(healthEndpoint, controller.signal);
        if (controller.signal.aborted) {
          return;
        }
        const nextState = resolveDesktopConnectivityState({
          isOnline: true,
          reachability,
          healthOrigin,
        });
        setConnectivity(nextState);
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        throw error;
      } finally {
        if (checkControllerRef.current === controller) {
          checkControllerRef.current = null;
        }
      }
    },
    [healthEndpoint, healthOrigin],
  );

  useEffect(() => {
    if (!isDesktopRuntime()) {
      return;
    }

    const initialCheckId = window.setTimeout(() => {
      void refreshConnectivity();
    }, 0);

    const handleOnline = () => {
      void refreshConnectivity();
    };
    const handleOffline = () => {
      checkControllerRef.current?.abort();
      setConnectivity({ kind: "offline", healthOrigin });
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.clearTimeout(initialCheckId);
      checkControllerRef.current?.abort();
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [healthOrigin, refreshConnectivity]);

  if (
    !isDesktopRuntime() ||
    connectivity.kind === "online" ||
    connectivity.kind === "checking"
  ) {
    return null;
  }

  const copy =
    connectivity.kind === "offline"
      ? language === "fr"
        ? {
            title: "Connexion Internet indisponible",
            detail:
              "L’application bureau reste ouverte localement. Rebranchez l’appareil au réseau, puis réessayez pour reprendre les appels API et l’authentification.",
            retry: "Réessayer",
          }
        : {
            title: "Internet connection unavailable",
            detail:
              "The desktop app remains open locally. Reconnect this device to the network, then retry to resume API calls and authentication.",
            retry: "Retry",
          }
      : language === "fr"
      ? {
          title: "API inaccessible",
          detail:
            healthOrigin === null
              ? "Internet semble disponible, mais la vérification de l’API a échoué. Vérifiez que le service AI Value Studio est démarré et que CORS autorise app://studio, puis réessayez."
              : `Internet semble disponible, mais l’API AI Value Studio ne répond pas sur ${healthOrigin}. Vérifiez que le service est démarré et que CORS autorise app://studio, puis réessayez.`,
          retry: "Réessayer la connexion",
        }
      : {
          title: "API unreachable",
          detail:
            healthOrigin === null
              ? "Internet appears available, but the API reachability check failed. Verify that the AI Value Studio service is running and that CORS allows app://studio, then retry."
              : `Internet appears available, but the AI Value Studio API is not responding at ${healthOrigin}. Verify that the service is running and that CORS allows app://studio, then retry.`,
          retry: "Retry connection",
        };

  return (
    <div className="rounded-2xl border border-[var(--studio-warning)] bg-[var(--studio-surface)] px-4 py-3 text-sm shadow-[var(--shadow-sm)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-semibold text-[var(--studio-foreground)]">{copy.title}</p>
          <p className="text-[var(--studio-muted)]">{copy.detail}</p>
        </div>
        <Button
          variant="secondary"
          onClick={() => {
            void refreshConnectivity();
          }}
        >
          {copy.retry}
        </Button>
      </div>
    </div>
  );
}
