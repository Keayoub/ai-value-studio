export type CursorPage<T> = {
  items: T[];
  next_cursor: string | null;
};

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export type ProblemDetail = {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string;
  request_id: string;
};

export type MembershipStatus = "active" | "invited" | "disabled";
export type WorkspaceRole = "Consultant" | "Sponsor" | "Contributor" | "WorkspaceAdmin";
export type ProgramStatus =
  | "Draft"
  | "Discovery"
  | "Assessment"
  | "Prioritization"
  | "Decision"
  | "Closed";
export type UseCaseStatus =
  | "Draft"
  | "InProgress"
  | "Submitted"
  | "ChangesRequested"
  | "Approved"
  | "Rejected";
export type ProgramAssignmentRole = "Consultant" | "Sponsor" | "Contributor";
export type AuthMode = "dev" | "entra";

export type WorkspaceSummary = {
  id: string;
  name: string;
  sector: string | null;
  country_region: string | null;
  size_band: string | null;
  default_language: string;
  description: string | null;
  branding_json: {
    primary_color?: string | null;
    secondary_color?: string | null;
    logo_url?: string | null;
    wordmark?: string | null;
  } | null;
  confidentiality_policy: string;
  status: "active" | "archived";
  ai_assistance_enabled: boolean;
  ai_assistance_available: boolean;
  ai_assistance_consent_at: string | null;
  ai_assistance_consent_by_subject_id: string | null;
  ai_assistance_data_processing_note: string | null;
  created_by_subject_id: string;
  created_at: string;
  updated_at: string;
  my_role: WorkspaceRole;
  my_membership_status: MembershipStatus;
};

export type WorkspaceMember = {
  membership_id: string;
  workspace_id: string;
  role: WorkspaceRole;
  status: MembershipStatus;
  created_at: string;
  updated_at: string;
  identity: {
    id: string;
    subject: string;
    issuer: string;
    tenant_id: string;
    oid: string;
    display_name: string | null;
    email: string | null;
  };
};

export type Program = {
  id: string;
  workspace_id: string;
  name: string;
  strategic_objective: string | null;
  departments: string[];
  period_start: string | null;
  period_end: string | null;
  sponsor_membership_id: string | null;
  consultant_membership_id: string | null;
  target_use_case_count: number | null;
  questionnaire_template_version_id: string | null;
  confidentiality_level: string;
  status: ProgramStatus;
  created_by_subject_id: string;
  created_at: string;
  updated_at: string;
};

export type ProgramMember = {
  id: string;
  workspace_id: string;
  program_id: string;
  membership_id: string;
  assignment_role: ProgramAssignmentRole;
  created_by_subject_id: string;
  created_at: string;
  updated_at: string;
};

export type UseCase = {
  id: string;
  workspace_id: string;
  program_id: string;
  title: string;
  department: string | null;
  owner_membership_id: string | null;
  status: UseCaseStatus;
  recommendation: string | null;
  category: string | null;
  priority_score: number | null;
  score_version: number | null;
  confidence_level: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  current_assessment_version: number | null;
  created_by_subject_id: string;
  created_at: string;
  updated_at: string;
};

export type ReviewRecommendation = "Go" | "Pilot" | "Defer" | "Reject";
export type ReviewStatus = "Submitted" | "ChangesRequested" | "Approved" | "Rejected";
export type ReviewDecision = "Approved" | "Rejected" | "ChangesRequested";
export type DocumentType = "ExecutiveBrief" | "PilotCharter" | "AMOAImplementationPlan";
export type DocumentStatus = "Draft" | "InReview" | "Approved" | "Superseded";
export type DocumentFormat = "markdown" | "pdf";

export type ReviewActor = {
  subject_id: string;
  display_name: string | null;
  role: WorkspaceRole | string | null;
};

export type ApprovalRecord = {
  id: string;
  review_id: string;
  use_case_id: string;
  decision: ReviewDecision;
  decision_reason: string;
  approver: ReviewActor;
  decided_at: string;
  idempotency_key: string;
};

export type ReviewRecord = {
  id: string;
  use_case_id: string;
  assessment_version_id: string;
  assessment_version: number;
  status: ReviewStatus;
  recommendation: ReviewRecommendation;
  summary: string;
  risks: string[];
  submitted_by: ReviewActor;
  submitted_at: string;
  decided_by: ReviewActor | null;
  decided_at: string | null;
  decision_reason: string | null;
  approval: ApprovalRecord | null;
};

export type ReviewComment = {
  id: string;
  review_id: string;
  use_case_id: string;
  parent_comment_id: string | null;
  body: string;
  author: ReviewActor;
  created_at: string;
};

export type ReviewState = {
  review: ReviewRecord | null;
  review_history: ReviewRecord[];
  comments: ReviewComment[];
  can_submit_review: boolean;
  can_comment: boolean;
  can_decide: boolean;
  can_create_new_draft: boolean;
};

export type ReviewInboxItem = {
  review_id: string;
  use_case_id: string;
  program_id: string;
  use_case_title: string;
  program_name: string;
  assessment_version: number;
  status: ReviewStatus;
  recommendation: ReviewRecommendation;
  submitted_at: string;
  submitted_by: ReviewActor;
  decision_reason: string | null;
};

export type ScoreDimension =
  | "business_value"
  | "current_friction"
  | "data_feasibility"
  | "technical_feasibility"
  | "adoption_potential"
  | "risk_governance";

export type ValueScenario = {
  name: "conservative" | "baseline" | "optimistic" | string;
  annual_time_value: number;
  error_avoidance_value: number;
  revenue_capacity_value: number;
  gross_value: number;
  net_annual_value: number;
  npv_3y: number;
  payback_months: number | null;
};

export type ValueSensitivity = {
  lever: "time_saved_hours" | "error_reduction_rate" | "revenue_capacity_value" | string;
  baseline_net_annual_value: number;
  low_net_annual_value: number;
  high_net_annual_value: number;
  low_delta: number;
  high_delta: number;
  low_npv_3y: number;
  high_npv_3y: number;
};

export type ValueAssessment = {
  id: string | null;
  workspace_id: string;
  use_case_id: string;
  assessment_version_id: string;
  persisted: boolean;
  annual_volume: number;
  time_saved_hours: number;
  hourly_cost: number;
  error_reduction_rate: number;
  average_error_cost: number;
  revenue_capacity_value: number;
  estimated_annual_cost: number;
  time_to_impact_months: number;
  primary_kpi: string;
  kpi_target: string;
  confidence: string;
  currency: string;
  calculation_version: string;
  annual_time_value: number;
  error_avoidance_value: number;
  gross_value: number;
  net_annual_value: number;
  npv_3y: number;
  payback_months: number | null;
  scenarios: ValueScenario[];
  sensitivities: ValueSensitivity[];
  input_snapshot: Record<string, JsonValue>;
  source_snapshot: Record<string, JsonValue>;
  created_at: string | null;
  updated_at: string | null;
};

export type ScoreConfiguration = {
  id: string;
  workspace_id: string;
  version: number;
  is_active: boolean;
  weights: Record<ScoreDimension, number>;
  thresholds: Record<string, number>;
  created_at: string;
  updated_at: string;
};

export type ScorecardDimension = {
  id: string;
  dimension: ScoreDimension;
  weight: number;
  score: number;
  source: string;
  justification: string;
  confidence: string;
  is_manual_override: boolean;
  override_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type ScorecardVersion = {
  id: string;
  workspace_id: string;
  use_case_id: string;
  assessment_version_id: string;
  value_assessment_id: string;
  score_configuration_version_id: string;
  version: number;
  priority_score: number;
  readiness_average: number;
  category: "Quick Win" | "Strategic Bet" | "Foundation" | "Defer" | "Reject" | string;
  risk_profile: "Low" | "Medium" | "High" | "Critical" | string;
  confidence_level: string;
  calculation_version: string;
  manual_override: boolean;
  override_reason: string | null;
  input_snapshot: Record<string, JsonValue>;
  formula_snapshot: Record<string, JsonValue>;
  dimensions: ScorecardDimension[];
  created_by_subject_id: string;
  created_at: string;
  updated_at: string;
};

export type UseCaseScorecards = {
  value_assessment: ValueAssessment;
  score_configuration: ScoreConfiguration;
  current_scorecard: ScorecardVersion | null;
  history: ScorecardVersion[];
  read_only: boolean;
  can_override: boolean;
};

export type PortfolioProgramFilterOption = {
  id: string;
  name: string;
  count: number;
};

export type PortfolioValueFilterOption = {
  value: string;
  label: string;
  count: number;
};

export type PortfolioAppliedFilters = {
  program_id: string | null;
  status: UseCaseStatus | null;
  department: string | null;
  risk_profile: string | null;
};

export type PortfolioAvailableFilters = {
  programs: PortfolioProgramFilterOption[];
  statuses: PortfolioValueFilterOption[];
  departments: PortfolioValueFilterOption[];
  risks: PortfolioValueFilterOption[];
};

export type PortfolioSummary = {
  total_items: number;
  category_counts: Record<string, number>;
};

export type PortfolioItem = {
  workspace_id: string;
  program_id: string;
  use_case_id: string;
  program_name: string;
  use_case_title: string;
  department: string | null;
  status: UseCaseStatus;
  recommendation: string | null;
  category: "Quick Win" | "Strategic Bet" | "Foundation" | "Defer" | "Reject" | string;
  category_explanation_fr: string;
  priority_score: number;
  score_version: number;
  confidence_level: string;
  business_value_score: number;
  readiness_average: number;
  matrix_x: number;
  matrix_y: number;
  risk_profile: "Low" | "Medium" | "High" | "Critical" | string;
  risk_color: string;
  risk_shape: "circle" | "square" | "diamond" | "triangle" | string;
  risk_pattern: string;
  effort_band: "low" | "medium" | "high" | string | null;
  effort_label_fr: string | null;
  currency: string;
  net_annual_value: number;
  updated_at: string;
};

export type PortfolioResponse = {
  items: PortfolioItem[];
  summary: PortfolioSummary;
  applied_filters: PortfolioAppliedFilters;
  available_filters: PortfolioAvailableFilters;
};

export type DocumentEligibility = {
  can_generate_markdown: boolean;
  can_generate_pdf: boolean;
  markdown_reason: string | null;
  pdf_reason: string | null;
  source_assessment_version: number | null;
  source_scorecard_version: number | null;
  source_review_status: ReviewStatus | null;
};

export type GeneratedDocumentVersion = {
  id: string;
  document_id: string;
  version_no: number;
  format: DocumentFormat;
  storage_key: string;
  sha256: string;
  file_size_bytes: number;
  source_assessment_version_no: number;
  source_scorecard_version_no: number;
  source_review_id: string;
  source_review_status: ReviewStatus;
  ai_assisted_sections: Array<{
    section_id: string;
    title: string;
    source_fields: string[];
    marker: string;
  }>;
  approved_by_subject_id: string | null;
  approved_at: string | null;
  created_by_subject_id: string;
  created_at: string;
  updated_at: string;
  metadata_diff: string[];
};

export type GeneratedDocument = {
  id: string | null;
  use_case_id: string;
  type: DocumentType;
  language: string;
  status: DocumentStatus;
  current_version_no: number | null;
  current_version: GeneratedDocumentVersion | null;
  versions: GeneratedDocumentVersion[];
  eligibility: DocumentEligibility;
};

export type MeResponse = {
  subject: string;
  issuer: string;
  tenant_id: string;
  oid: string;
  display_name: string | null;
  email: string | null;
  token_roles: WorkspaceRole[];
  permitted_workspace_ids: string[];
  memberships: Array<{
    membership_id: string;
    workspace_id: string;
    workspace_name: string;
    role: WorkspaceRole;
    status: MembershipStatus;
    permissions: string[];
  }>;
};

export type AnswerSource = "human" | "ai_assisted";
export type AssessmentStatus = "Draft" | "Submitted";

export type WizardQuestion = {
  key: string;
  field_type: string;
  label: string;
  help_text: string | null;
  placeholder: string | null;
  options: Array<{ value: string; label: string }>;
  schema: Record<string, JsonValue>;
  step_index: number;
  required: boolean;
  visible: boolean;
  read_only: boolean;
  contributor_editable: boolean;
  value: JsonValue | null;
  evidence_text: string | null;
  confidence: string | null;
  captured_for_membership_id: string | null;
  source: AnswerSource | null;
  updated_at: string | null;
};

export type WizardStep = {
  index: number;
  key: string;
  title: string;
  purpose: string;
  available: boolean;
  optional: boolean;
  questions: WizardQuestion[];
};

export type WizardTemplateVersion = {
  id: string;
  template_key: string;
  version: number;
  locale: string;
  title: string;
  description: string | null;
  steps: WizardStep[];
};

export type StepValuePreview = {
  annual_time_value: number;
  error_avoidance_value: number;
  gross_value: number;
  net_value: number;
};

export type DerivedAssessmentState = {
  step4_preview: StepValuePreview | null;
  risk_profile: "Low" | "Medium" | "High" | "Critical" | null;
  missing_information: string[];
  sponsor_name: string | null;
};

export type StepValidationError = {
  question_key: string;
  message: string;
};

export type StepValidationResponse = {
  step: number;
  is_valid: boolean;
  errors: StepValidationError[];
  derived: DerivedAssessmentState;
};

export type AssessmentSummary = {
  id: string;
  use_case_id: string;
  workspace_id: string;
  version: number;
  status: AssessmentStatus;
  interview_mode: boolean;
  respondent_membership_id: string | null;
  created_by_subject_id: string;
  submitted_by_subject_id: string | null;
  submitted_at: string | null;
  approved_by_subject_id: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
  can_edit: boolean;
  can_submit: boolean;
  editor_role: string;
};

export type Hypothesis = {
  id: string;
  statement: string;
  kind: string;
  status: string;
};

export type AssessmentEnvelope = {
  assessment: AssessmentSummary;
  template: WizardTemplateVersion;
  derived: DerivedAssessmentState;
  validation: StepValidationResponse[];
  hypotheses: Hypothesis[];
};

export type KickstartProposal = {
  source: "ai_assisted";
  problem_statement: string;
  ai_solution: string;
  kpi_proposals: string[];
  value_hypotheses: string[];
  risks: string[];
  missing_info: string[];
};

export type KickstartSuggestion = {
  proposal: KickstartProposal;
  provider: string;
  model: string;
  generated_at: string;
};

export type WizardAnswerResponse = {
  question_key: string;
  value: JsonValue;
  evidence_text: string | null;
  confidence: string | null;
  captured_for_membership_id: string | null;
  source: AnswerSource;
  updated_at: string;
};
