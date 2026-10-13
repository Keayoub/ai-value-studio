import type { MeResponse, Program, UseCase, WorkspaceMember, WorkspaceSummary } from "@/features/api/types";

export type ViewerFlags = {
  canManageWorkspace: boolean;
  canManagePrograms: boolean;
  canManageUseCases: boolean;
  canViewMembers: boolean;
  membershipId: string | null;
  role: string | null;
};

export function getViewerFlags(
  me: MeResponse | null,
  workspaceId: string | null,
): ViewerFlags {
  if (!me || !workspaceId) {
    return {
      canManageWorkspace: false,
      canManagePrograms: false,
      canManageUseCases: false,
      canViewMembers: false,
      membershipId: null,
      role: null,
    };
  }
  const membership = me.memberships.find((item) => item.workspace_id === workspaceId);
  const permissions = new Set(membership?.permissions ?? []);
  return {
    canManageWorkspace: permissions.has("workspace:update"),
    canManagePrograms: permissions.has("program:update"),
    canManageUseCases: permissions.has("use-case:update"),
    canViewMembers: permissions.has("members:read"),
    membershipId: membership?.membership_id ?? null,
    role: membership?.role ?? null,
  };
}

export function canAccessWorkspace(me: MeResponse | null, workspaceId: string | null): boolean {
  return Boolean(workspaceId && me?.permitted_workspace_ids.includes(workspaceId));
}

export function resolveVisibleProgram(
  programs: Program[],
  programId: string | null,
): Program | null {
  if (!programId) {
    return null;
  }
  return programs.find((program) => program.id === programId) ?? null;
}

export function resolveVisibleUseCase(useCases: UseCase[], useCaseId: string | null): UseCase | null {
  if (!useCaseId) {
    return null;
  }
  return useCases.find((useCase) => useCase.id === useCaseId) ?? null;
}

export function resolveMembershipLabel(
  members: WorkspaceMember[],
  membershipId: string | null | undefined,
): string {
  if (!membershipId) {
    return "—";
  }
  return (
    members.find((member) => member.membership_id === membershipId)?.identity.display_name ??
    membershipId
  );
}

export function workspaceDisplayLanguage(workspace: WorkspaceSummary | null): "fr" | "en" {
  return workspace?.default_language.toLowerCase().startsWith("en") ? "en" : "fr";
}
