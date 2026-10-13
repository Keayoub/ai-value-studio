import test from "node:test";
import assert from "node:assert/strict";

import {
  canAccessWorkspace,
  getViewerFlags,
  resolveVisibleProgram,
  resolveVisibleUseCase,
  workspaceDisplayLanguage,
} from "../../src/features/auth/guards";
import type { MeResponse, Program, UseCase, WorkspaceSummary } from "../../src/features/api/types";

const me: MeResponse = {
  subject: "dev:consultant",
  issuer: "dev",
  tenant_id: "dev",
  oid: "consultant",
  display_name: "Local Consultant",
  email: "consultant@local.dev",
  token_roles: ["Consultant"],
  permitted_workspace_ids: ["workspace-a"],
  memberships: [
    {
      membership_id: "member-a",
      workspace_id: "workspace-a",
      workspace_name: "Workspace A",
      role: "Consultant",
      status: "active",
      permissions: ["workspace:read", "program:update", "use-case:update", "members:read"],
    },
  ],
};

test("viewer flags expose management permissions", () => {
  assert.equal(canAccessWorkspace(me, "workspace-a"), true);
  assert.equal(canAccessWorkspace(me, "workspace-b"), false);

  const flags = getViewerFlags(me, "workspace-a");
  assert.equal(flags.canManagePrograms, true);
  assert.equal(flags.canManageUseCases, true);
  assert.equal(flags.canViewMembers, true);
  assert.equal(flags.membershipId, "member-a");
});

test("visible entity resolvers return null for missing ids", () => {
  const programs: Program[] = [
    {
      id: "program-a",
      workspace_id: "workspace-a",
      name: "Program A",
      strategic_objective: null,
      departments: [],
      period_start: null,
      period_end: null,
      sponsor_membership_id: null,
      consultant_membership_id: null,
      target_use_case_count: null,
      questionnaire_template_version_id: null,
      confidentiality_level: "internal-only",
      status: "Draft",
      created_by_subject_id: "subject-a",
      created_at: "",
      updated_at: "",
    },
  ];
  const useCases: UseCase[] = [
    {
      id: "use-case-a",
      workspace_id: "workspace-a",
      program_id: "program-a",
      title: "Use Case A",
      department: null,
      owner_membership_id: null,
      status: "Draft",
      recommendation: null,
      category: null,
      priority_score: null,
      score_version: null,
      confidence_level: null,
      submitted_at: null,
      approved_at: null,
      current_assessment_version: null,
      created_by_subject_id: "subject-a",
      created_at: "",
      updated_at: "",
    },
  ];

  assert.equal(resolveVisibleProgram(programs, "program-a")?.name, "Program A");
  assert.equal(resolveVisibleProgram(programs, "program-b"), null);
  assert.equal(resolveVisibleUseCase(useCases, "use-case-a")?.title, "Use Case A");
  assert.equal(resolveVisibleUseCase(useCases, "use-case-b"), null);
});

test("workspace display language stays French-first until a workspace language is loaded", () => {
  assert.equal(workspaceDisplayLanguage(null), "fr");

  const frenchWorkspace: WorkspaceSummary = {
    id: "workspace-fr",
    name: "Espace FR",
    sector: null,
    country_region: null,
    size_band: null,
    description: null,
    default_language: "fr-CA",
    branding_json: null,
    confidentiality_policy: "internal-only",
    status: "active",
    ai_assistance_enabled: false,
    ai_assistance_available: false,
    ai_assistance_consent_at: null,
    ai_assistance_consent_by_subject_id: null,
    ai_assistance_data_processing_note: null,
    created_by_subject_id: "subject-a",
    created_at: "",
    updated_at: "",
    my_role: "WorkspaceAdmin",
    my_membership_status: "active",
  };

  assert.equal(workspaceDisplayLanguage(frenchWorkspace), "fr");

  const englishWorkspace: WorkspaceSummary = {
    ...frenchWorkspace,
    id: "workspace-en",
    name: "Workspace EN",
    default_language: "en-US",
  };

  assert.equal(workspaceDisplayLanguage(englishWorkspace), "en");
});
