import type {
  AssessmentEnvelope,
  CursorPage,
  DocumentFormat,
  DocumentType,
  GeneratedDocument,
  GeneratedDocumentVersion,
  JsonValue,
  KickstartSuggestion,
  MeResponse,
  ProblemDetail,
  Program,
  PortfolioResponse,
  ProgramMember,
  ProgramStatus,
  ReviewComment,
  ReviewDecision,
  ReviewInboxItem,
  ReviewRecommendation,
  ReviewState,
  ScoreDimension,
  StepValidationResponse,
  UseCase,
  UseCaseScorecards,
  UseCaseStatus,
  ValueAssessment,
  WizardAnswerResponse,
  WorkspaceMember,
  WorkspaceSummary,
} from "@/features/api/types";

export class ApiClientError extends Error {
  readonly problem: ProblemDetail;

  constructor(problem: ProblemDetail) {
    super(problem.detail);
    this.name = "ApiClientError";
    this.problem = problem;
  }
}

type RequestOptions = RequestInit & {
  headers?: HeadersInit;
};

function fallbackFilenameForContentType(contentType: string) {
  if (contentType.includes("pdf")) {
    return "document.pdf";
  }
  if (contentType.includes("markdown")) {
    return "document.md";
  }
  if (contentType.startsWith("text/")) {
    return "document.txt";
  }
  return "document.bin";
}

function parseContentDispositionFilename(
  contentDisposition: string,
  contentType: string,
) {
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const filenameMatch = contentDisposition.match(/filename="([^"]+)"/i);
  if (filenameMatch?.[1]) {
    return filenameMatch[1];
  }
  return fallbackFilenameForContentType(contentType);
}

export class BrowserApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly getAuthHeaders: () => Promise<Record<string, string>>,
  ) {}

  async getMe(): Promise<MeResponse> {
    return this.request<MeResponse>("/me");
  }

  async listWorkspaces(): Promise<CursorPage<WorkspaceSummary>> {
    return this.request<CursorPage<WorkspaceSummary>>("/workspaces");
  }

  async createWorkspace(payload: {
    name: string;
    default_language: string;
    confidentiality_policy: string;
    description?: string;
  }): Promise<WorkspaceSummary> {
    return this.request("/workspaces", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getWorkspace(workspaceId: string): Promise<WorkspaceSummary> {
    return this.request<WorkspaceSummary>(`/workspaces/${workspaceId}`);
  }

  async listWorkspaceMembers(workspaceId: string): Promise<CursorPage<WorkspaceMember>> {
    return this.request<CursorPage<WorkspaceMember>>(`/workspaces/${workspaceId}/members`);
  }

  async listPrograms(workspaceId: string): Promise<CursorPage<Program>> {
    return this.request<CursorPage<Program>>(`/workspaces/${workspaceId}/programs`);
  }

  async getPortfolio(
    workspaceId: string,
    filters: {
      programId?: string | null;
      status?: string | null;
      department?: string | null;
      risk?: string | null;
    } = {},
  ): Promise<PortfolioResponse> {
    const query = new URLSearchParams();
    if (filters.programId) {
      query.set("program_id", filters.programId);
    }
    if (filters.status) {
      query.set("status", filters.status);
    }
    if (filters.department) {
      query.set("department", filters.department);
    }
    if (filters.risk) {
      query.set("risk", filters.risk);
    }
    const suffix = query.size ? `?${query.toString()}` : "";
    return this.request<PortfolioResponse>(`/workspaces/${workspaceId}/portfolio${suffix}`);
  }

  async createProgram(
    workspaceId: string,
    payload: {
      name: string;
      strategic_objective?: string;
      sponsor_membership_id?: string | null;
      consultant_membership_id?: string | null;
      target_use_case_count?: number | null;
      departments?: string[];
    },
  ): Promise<Program> {
    return this.request<Program>(`/workspaces/${workspaceId}/programs`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getProgram(workspaceId: string, programId: string): Promise<Program> {
    return this.request<Program>(`/workspaces/${workspaceId}/programs/${programId}`);
  }

  async updateProgram(
    workspaceId: string,
    programId: string,
    payload: Partial<{
      strategic_objective: string | null;
      sponsor_membership_id: string | null;
      consultant_membership_id: string | null;
      target_use_case_count: number | null;
      departments: string[] | null;
    }>,
  ): Promise<Program> {
    return this.request<Program>(`/workspaces/${workspaceId}/programs/${programId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async transitionProgram(
    workspaceId: string,
    programId: string,
    target_status: ProgramStatus,
  ): Promise<Program> {
    return this.request<Program>(`/workspaces/${workspaceId}/programs/${programId}/transition`, {
      method: "POST",
      body: JSON.stringify({ target_status }),
    });
  }

  async listProgramMembers(
    workspaceId: string,
    programId: string,
  ): Promise<CursorPage<ProgramMember>> {
    return this.request<CursorPage<ProgramMember>>(
      `/workspaces/${workspaceId}/programs/${programId}/members`,
    );
  }

  async assignProgramMember(
    workspaceId: string,
    programId: string,
    payload: { membership_id: string; assignment_role: string },
  ): Promise<ProgramMember> {
    return this.request<ProgramMember>(`/workspaces/${workspaceId}/programs/${programId}/members`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async listUseCases(workspaceId: string, programId: string): Promise<CursorPage<UseCase>> {
    return this.request<CursorPage<UseCase>>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases`,
    );
  }

  async createUseCase(
    workspaceId: string,
    programId: string,
    payload: {
      title: string;
      department?: string;
      owner_membership_id?: string | null;
      recommendation?: string;
    },
  ): Promise<UseCase> {
    return this.request<UseCase>(`/workspaces/${workspaceId}/programs/${programId}/use-cases`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getUseCase(workspaceId: string, programId: string, useCaseId: string): Promise<UseCase> {
    return this.request<UseCase>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}`,
    );
  }

  async updateUseCase(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    payload: Partial<{
      title: string;
      department: string | null;
      owner_membership_id: string | null;
      recommendation: string | null;
      category: string | null;
      confidence_level: string | null;
    }>,
  ): Promise<UseCase> {
    return this.request<UseCase>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    );
  }

  async transitionUseCase(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    target_status: UseCaseStatus,
  ): Promise<UseCase> {
    return this.request<UseCase>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/transition`,
      {
        method: "POST",
        body: JSON.stringify({ target_status }),
      },
    );
  }

  async createAssessment(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    payload: {
      interview_mode?: boolean;
      respondent_membership_id?: string | null;
      force_new_version?: boolean;
    } = {},
  ): Promise<AssessmentEnvelope> {
    return this.request<AssessmentEnvelope>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/assessments`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }

  async getCurrentAssessment(
    workspaceId: string,
    programId: string,
    useCaseId: string,
  ): Promise<AssessmentEnvelope> {
    return this.request<AssessmentEnvelope>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/assessments/current`,
    );
  }

  async getAssessment(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    assessmentId: string,
  ): Promise<AssessmentEnvelope> {
    return this.request<AssessmentEnvelope>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/assessments/${assessmentId}`,
    );
  }

  async upsertAssessmentAnswer(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    assessmentId: string,
    questionKey: string,
    payload: {
      value: JsonValue;
      evidence_text?: string | null;
      confidence?: string | null;
      captured_for_membership_id?: string | null;
      source?: "human" | "ai_assisted";
      confirm_overwrite_ai_assisted?: boolean;
    },
  ): Promise<WizardAnswerResponse> {
    return this.request<WizardAnswerResponse>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/assessments/${assessmentId}/answers/${questionKey}`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    );
  }

  async generateAssessmentKickstart(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    assessmentId: string,
  ): Promise<KickstartSuggestion> {
    return this.request<KickstartSuggestion>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/assessments/${assessmentId}/kickstart`,
      {
        method: "POST",
      },
    );
  }

  async validateAssessmentStep(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    assessmentId: string,
    step: number,
  ): Promise<StepValidationResponse> {
    return this.request<StepValidationResponse>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/assessments/${assessmentId}/validate-step/${step}`,
      {
        method: "POST",
      },
    );
  }

  async submitAssessment(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    assessmentId: string,
  ): Promise<{ submitted: AssessmentEnvelope }> {
    return this.request<{ submitted: AssessmentEnvelope }>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/assessments/${assessmentId}/submit`,
      {
        method: "POST",
      },
    );
  }

  async getReviewState(
    workspaceId: string,
    programId: string,
    useCaseId: string,
  ): Promise<ReviewState> {
    return this.request<ReviewState>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/review`,
    );
  }

  async listReviewInbox(workspaceId: string): Promise<CursorPage<ReviewInboxItem>> {
    return this.request<CursorPage<ReviewInboxItem>>(`/workspaces/${workspaceId}/review-inbox`);
  }

  async createReview(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    payload: {
      recommendation: ReviewRecommendation;
      summary: string;
      risks: string[];
    },
  ): Promise<ReviewState> {
    return this.request<ReviewState>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/reviews`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }

  async createReviewComment(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    payload: {
      body: string;
      parent_comment_id?: string | null;
    },
  ): Promise<ReviewComment> {
    return this.request<ReviewComment>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/comments`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }

  async decideReview(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    reviewId: string,
    decision: ReviewDecision,
    decisionReason: string,
    idempotencyKey: string,
  ): Promise<ReviewState> {
    const action =
      decision === "Approved"
        ? "approve"
        : decision === "Rejected"
          ? "reject"
          : "request-changes";
    return this.request<ReviewState>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/reviews/${reviewId}/${action}`,
      {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ decision_reason: decisionReason }),
      },
    );
  }

  async getUseCaseScorecards(
    workspaceId: string,
    programId: string,
    useCaseId: string,
  ): Promise<UseCaseScorecards> {
    return this.request<UseCaseScorecards>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/scorecards`,
    );
  }

  async putValueAssessment(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    payload: Pick<
      ValueAssessment,
      | "annual_volume"
      | "time_saved_hours"
      | "hourly_cost"
      | "error_reduction_rate"
      | "average_error_cost"
      | "revenue_capacity_value"
      | "estimated_annual_cost"
      | "time_to_impact_months"
      | "primary_kpi"
      | "kpi_target"
      | "confidence"
      | "currency"
    >,
  ): Promise<UseCaseScorecards> {
    return this.request<UseCaseScorecards>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/value-assessment`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    );
  }

  async recalculateScorecards(
    workspaceId: string,
    programId: string,
    useCaseId: string,
  ): Promise<UseCaseScorecards> {
    return this.request<UseCaseScorecards>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/scorecards/recalculate`,
      {
        method: "POST",
      },
    );
  }

  async overrideScorecard(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    payload: { dimension: ScoreDimension; score: number; reason: string },
  ): Promise<UseCaseScorecards> {
    return this.request<UseCaseScorecards>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/scorecards/override`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }

  async listDocuments(
    workspaceId: string,
    programId: string,
    useCaseId: string,
  ): Promise<GeneratedDocument[]> {
    return this.request<GeneratedDocument[]>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/documents`,
    );
  }

  async generateDocument(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    payload: { type: DocumentType; format: DocumentFormat; language?: string },
    idempotencyKey: string,
  ): Promise<GeneratedDocument> {
    return this.request<GeneratedDocument>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/documents`,
      {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({
          language: payload.language ?? "fr",
          type: payload.type,
          format: payload.format,
        }),
      },
    );
  }

  async listDocumentVersions(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    documentId: string,
  ): Promise<GeneratedDocumentVersion[]> {
    return this.request<GeneratedDocumentVersion[]>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/documents/${documentId}/versions`,
    );
  }

  async approveDocument(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    documentId: string,
  ): Promise<GeneratedDocument> {
    return this.request<GeneratedDocument>(
      `/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/documents/${documentId}/approve`,
      {
        method: "POST",
      },
    );
  }

  async downloadDocumentVersion(
    workspaceId: string,
    programId: string,
    useCaseId: string,
    versionId: string,
  ): Promise<{
    blob: Blob;
    filename: string;
    sha256: string | null;
    contentType: string;
  }> {
    const authHeaders = await this.getAuthHeaders();
    const headers = new Headers(authHeaders);
    const response = await fetch(
      `${this.baseUrl}/workspaces/${workspaceId}/programs/${programId}/use-cases/${useCaseId}/document-versions/${versionId}/download`,
      { method: "GET", headers },
    );
    const contentType = response.headers.get("content-type") ?? "application/octet-stream";
    if (!response.ok) {
      throw new ApiClientError(await parseProblemDetail(response, contentType, "document-download"));
    }
    const contentDisposition = response.headers.get("content-disposition") ?? "";
    return {
      blob: await response.blob(),
      filename: parseContentDispositionFilename(contentDisposition, contentType),
      sha256: response.headers.get("x-document-sha256"),
      contentType,
    };
  }

  private async request<T>(path: string, init: RequestOptions = {}): Promise<T> {
    const authHeaders = await this.getAuthHeaders();
    const headers = new Headers(init.headers ?? {});
    headers.set("Accept", "application/json");
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    for (const [key, value] of Object.entries(authHeaders)) {
      headers.set(key, value);
    }

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        headers,
      });
    } catch (error) {
      throw new ApiClientError({
        type: "about:blank",
        title: "Network Error",
        status: 0,
        detail: error instanceof Error ? error.message : "Network request failed.",
        instance: path,
        request_id: "client",
      });
    }

    const contentType = response.headers.get("content-type") ?? "";
    if (!response.ok) {
      throw new ApiClientError(await parseProblemDetail(response, contentType, path));
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }
}

async function parseProblemDetail(
  response: Response,
  contentType: string,
  instance: string,
): Promise<ProblemDetail> {
  if (contentType.includes("application/json")) {
    try {
      const data = (await response.json()) as Partial<ProblemDetail>;
      if (isProblemDetail(data)) {
        return data;
      }
    } catch {
      // Fall through to generic detail.
    }
  }
  return {
    type: "about:blank",
    title: response.statusText || "Request Failed",
    status: response.status,
    detail: `Unexpected response (${response.status}).`,
    instance,
    request_id: response.headers.get("x-request-id") ?? "unknown",
  };
}

function isProblemDetail(value: Partial<ProblemDetail>): value is ProblemDetail {
  return (
    typeof value.type === "string" &&
    typeof value.title === "string" &&
    typeof value.status === "number" &&
    typeof value.detail === "string" &&
    typeof value.instance === "string" &&
    typeof value.request_id === "string"
  );
}
