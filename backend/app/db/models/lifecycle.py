from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from app.db.base import TimestampedModel, UUIDPrimaryKeyModel, utc_now
from sqlalchemy import JSON, Boolean, Column, DateTime, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


class ProgramStatus(StrEnum):
    DRAFT = "Draft"
    DISCOVERY = "Discovery"
    ASSESSMENT = "Assessment"
    PRIORITIZATION = "Prioritization"
    DECISION = "Decision"
    CLOSED = "Closed"


class ProgramConfidentialityLevel(StrEnum):
    STANDARD = "standard"
    INTERNAL_ONLY = "internal-only"
    RESTRICTED = "restricted"
    REGULATED = "regulated"


class ProgramAssignmentRole(StrEnum):
    CONSULTANT = "Consultant"
    SPONSOR = "Sponsor"
    CONTRIBUTOR = "Contributor"


class UseCaseStatus(StrEnum):
    DRAFT = "Draft"
    IN_PROGRESS = "InProgress"
    SUBMITTED = "Submitted"
    CHANGES_REQUESTED = "ChangesRequested"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class AssessmentStatus(StrEnum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"


class ReviewRecommendation(StrEnum):
    GO = "Go"
    PILOT = "Pilot"
    DEFER = "Defer"
    REJECT = "Reject"


class ReviewStatus(StrEnum):
    SUBMITTED = "Submitted"
    CHANGES_REQUESTED = "ChangesRequested"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class ApprovalDecision(StrEnum):
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CHANGES_REQUESTED = "ChangesRequested"


class AnswerSource(StrEnum):
    HUMAN = "human"
    AI_ASSISTED = "ai_assisted"


class HypothesisKind(StrEnum):
    VALUE = "value"
    RISK = "risk"
    ASSUMPTION = "assumption"


class HypothesisStatus(StrEnum):
    OPEN = "open"
    VALIDATED = "validated"
    DISMISSED = "dismissed"


class ScoreDimension(StrEnum):
    BUSINESS_VALUE = "business_value"
    CURRENT_FRICTION = "current_friction"
    DATA_FEASIBILITY = "data_feasibility"
    TECHNICAL_FEASIBILITY = "technical_feasibility"
    ADOPTION_POTENTIAL = "adoption_potential"
    RISK_GOVERNANCE = "risk_governance"


class DocumentType(StrEnum):
    EXECUTIVE_BRIEF = "ExecutiveBrief"
    PILOT_CHARTER = "PilotCharter"
    AMOA_IMPLEMENTATION_PLAN = "AMOAImplementationPlan"


class DocumentStatus(StrEnum):
    DRAFT = "Draft"
    IN_REVIEW = "InReview"
    APPROVED = "Approved"
    SUPERSEDED = "Superseded"


class DocumentFormat(StrEnum):
    MARKDOWN = "markdown"
    PDF = "pdf"


class ProgramBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    name: str = Field(min_length=1, max_length=200, index=True)
    strategic_objective: str | None = Field(default=None, max_length=2000)
    departments_json: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    period_start: date | None = Field(default=None)
    period_end: date | None = Field(default=None)
    sponsor_membership_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="workspace_memberships.id",
        index=True,
    )
    consultant_membership_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="workspace_memberships.id",
        index=True,
    )
    target_use_case_count: int | None = Field(default=None, ge=0)
    questionnaire_template_version_id: uuid.UUID | None = Field(default=None)
    confidentiality_level: ProgramConfidentialityLevel = Field(
        default=ProgramConfidentialityLevel.INTERNAL_ONLY,
        max_length=32,
    )
    status: ProgramStatus = Field(default=ProgramStatus.DRAFT, max_length=32)


class Program(ProgramBase, UUIDPrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "programs"

    created_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id", nullable=False, index=True
    )


class ProgramMemberBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    program_id: uuid.UUID = Field(foreign_key="programs.id", nullable=False, index=True)
    membership_id: uuid.UUID = Field(
        foreign_key="workspace_memberships.id",
        nullable=False,
        index=True,
    )
    assignment_role: ProgramAssignmentRole = Field(max_length=64)


class ProgramMember(ProgramMemberBase, UUIDPrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "program_members"
    __table_args__ = (
        UniqueConstraint(
            "program_id",
            "membership_id",
            name="uq_program_member_program_membership",
        ),
    )

    created_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id", nullable=False, index=True
    )


class UseCaseBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    program_id: uuid.UUID = Field(foreign_key="programs.id", nullable=False, index=True)
    title: str = Field(min_length=1, max_length=200, index=True)
    department: str | None = Field(default=None, max_length=200)
    owner_membership_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="workspace_memberships.id",
        index=True,
    )
    status: UseCaseStatus = Field(default=UseCaseStatus.DRAFT, max_length=32)
    recommendation: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=120)
    priority_score: float | None = Field(
        default=None,
        sa_column=Column(Numeric(8, 3), nullable=True),
    )
    score_version: int | None = Field(default=None, ge=1)
    confidence_level: str | None = Field(default=None, max_length=120)
    submitted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    approved_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    current_assessment_version: int | None = Field(default=None, ge=1)


class UseCase(UseCaseBase, UUIDPrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "use_cases"

    created_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id", nullable=False, index=True
    )


class QuestionnaireTemplateVersionBase(SQLModel):
    workspace_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="workspaces.id",
        nullable=True,
        index=True,
    )
    template_key: str = Field(min_length=1, max_length=80, index=True)
    version: int = Field(ge=1)
    locale: str = Field(min_length=2, max_length=16, default="fr")
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, default=True),
    )
    template_schema_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column("schema_json", JSON, nullable=False),
    )


class QuestionnaireTemplateVersion(
    QuestionnaireTemplateVersionBase,
    UUIDPrimaryKeyModel,
    TimestampedModel,
    table=True,
):
    __tablename__ = "questionnaire_template_versions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "template_key",
            "version",
            name="uq_questionnaire_template_workspace_key_version",
        ),
    )

    created_by_subject_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="identity_subjects.id",
        nullable=True,
        index=True,
    )


class QuestionDefinitionBase(SQLModel):
    template_version_id: uuid.UUID = Field(
        foreign_key="questionnaire_template_versions.id",
        nullable=False,
        index=True,
    )
    step_index: int = Field(ge=0, le=8, index=True)
    sort_order: int = Field(ge=0, default=0)
    question_key: str = Field(min_length=1, max_length=120)
    field_type: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=300)
    help_text: str | None = Field(default=None, max_length=2000)
    placeholder: str | None = Field(default=None, max_length=300)
    options_json: list[dict[str, str]] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    validation_schema_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column("schema_json", JSON, nullable=False),
    )
    conditional_rules_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column("conditional_json", JSON, nullable=True),
    )
    ui_config_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column("ui_json", JSON, nullable=True),
    )
    contributor_editable: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, default=True),
    )


class QuestionDefinition(
    QuestionDefinitionBase,
    UUIDPrimaryKeyModel,
    TimestampedModel,
    table=True,
):
    __tablename__ = "question_definitions"
    __table_args__ = (
        UniqueConstraint(
            "template_version_id",
            "question_key",
            name="uq_question_definition_template_question_key",
        ),
    )


class AssessmentVersionBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    use_case_id: uuid.UUID = Field(foreign_key="use_cases.id", nullable=False, index=True)
    version: int = Field(ge=1)
    template_version_id: uuid.UUID = Field(
        foreign_key="questionnaire_template_versions.id",
        nullable=False,
        index=True,
    )
    status: AssessmentStatus = Field(default=AssessmentStatus.DRAFT, max_length=32)
    interview_mode: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )
    respondent_membership_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="workspace_memberships.id",
        index=True,
    )
    submission_snapshot_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column("snapshot_json", JSON, nullable=True),
    )
    submitted_by_subject_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="identity_subjects.id",
        index=True,
    )
    submitted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    approved_by_subject_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="identity_subjects.id",
        index=True,
    )
    approved_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class AssessmentVersion(
    AssessmentVersionBase,
    UUIDPrimaryKeyModel,
    TimestampedModel,
    table=True,
):
    __tablename__ = "assessment_versions"
    __table_args__ = (
        UniqueConstraint(
            "use_case_id",
            "version",
            name="uq_assessment_version_use_case_version",
        ),
    )

    created_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id",
        nullable=False,
        index=True,
    )


class AnswerBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    assessment_version_id: uuid.UUID = Field(
        foreign_key="assessment_versions.id",
        nullable=False,
        index=True,
    )
    question_key: str = Field(min_length=1, max_length=120)
    value_data_json: Any = Field(sa_column=Column("value_json", JSON, nullable=False))
    evidence_text: str | None = Field(default=None, max_length=2000)
    confidence: str | None = Field(default=None, max_length=120)
    entered_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id",
        nullable=False,
        index=True,
    )
    captured_for_membership_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="workspace_memberships.id",
        index=True,
    )
    source: AnswerSource = Field(default=AnswerSource.HUMAN, max_length=32)


class Answer(AnswerBase, UUIDPrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "answers"
    __table_args__ = (
        UniqueConstraint(
            "assessment_version_id",
            "question_key",
            name="uq_answer_assessment_question_key",
        ),
    )


class HypothesisBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    use_case_id: uuid.UUID = Field(foreign_key="use_cases.id", nullable=False, index=True)
    assessment_version_id: uuid.UUID = Field(
        foreign_key="assessment_versions.id",
        nullable=False,
        index=True,
    )
    statement: str = Field(min_length=1, max_length=2000)
    kind: HypothesisKind = Field(max_length=32)
    status: HypothesisStatus = Field(default=HypothesisStatus.OPEN, max_length=32)
    owner: str | None = Field(default=None, max_length=255)
    evidence_ref: str | None = Field(default=None, max_length=255)
    validated_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class Hypothesis(HypothesisBase, UUIDPrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "hypotheses"


class ReviewBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    use_case_id: uuid.UUID = Field(foreign_key="use_cases.id", nullable=False, index=True)
    assessment_version_id: uuid.UUID = Field(
        foreign_key="assessment_versions.id",
        nullable=False,
        index=True,
    )
    status: ReviewStatus = Field(default=ReviewStatus.SUBMITTED, max_length=32)
    recommendation: ReviewRecommendation = Field(max_length=16)
    summary: str = Field(min_length=1, max_length=4000)
    risks_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    submitted_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id",
        nullable=False,
        index=True,
    )
    submitted_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    decided_by_subject_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="identity_subjects.id",
        index=True,
    )
    decided_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    decision_reason: str | None = Field(default=None, max_length=4000)


class Review(ReviewBase, UUIDPrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint(
            "assessment_version_id",
            name="uq_review_assessment_version",
        ),
    )


class ReviewCommentBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    use_case_id: uuid.UUID = Field(foreign_key="use_cases.id", nullable=False, index=True)
    review_id: uuid.UUID = Field(foreign_key="reviews.id", nullable=False, index=True)
    parent_comment_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="review_comments.id",
        index=True,
    )
    body: str = Field(min_length=1, max_length=4000)
    author_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id",
        nullable=False,
        index=True,
    )


class ReviewComment(ReviewCommentBase, UUIDPrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "review_comments"


class ApprovalBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    use_case_id: uuid.UUID = Field(foreign_key="use_cases.id", nullable=False, index=True)
    review_id: uuid.UUID = Field(foreign_key="reviews.id", nullable=False, index=True)
    decision: ApprovalDecision = Field(max_length=32)
    decision_reason: str = Field(default="", max_length=4000)
    approver_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id",
        nullable=False,
        index=True,
    )
    decided_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    idempotency_key: str = Field(min_length=1, max_length=255)
    response_snapshot_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )


class Approval(ApprovalBase, UUIDPrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "approvals"
    __table_args__ = (
        UniqueConstraint(
            "review_id",
            name="uq_approval_review",
        ),
        UniqueConstraint(
            "approver_subject_id",
            "idempotency_key",
            name="uq_approval_approver_idempotency_key",
        ),
    )


class ValueAssessmentBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    use_case_id: uuid.UUID = Field(foreign_key="use_cases.id", nullable=False, index=True)
    assessment_version_id: uuid.UUID = Field(
        foreign_key="assessment_versions.id",
        nullable=False,
        index=True,
    )
    revision: int = Field(ge=1)
    annual_volume: float = Field(
        ge=0,
        sa_column=Column(Numeric(18, 2), nullable=False),
    )
    time_saved_hours: float = Field(
        ge=0,
        sa_column=Column(Numeric(18, 4), nullable=False),
    )
    hourly_cost: float = Field(
        ge=0,
        sa_column=Column(Numeric(18, 2), nullable=False),
    )
    error_reduction_rate: float = Field(
        ge=0,
        le=100,
        sa_column=Column(Numeric(10, 4), nullable=False),
    )
    average_error_cost: float = Field(
        ge=0,
        sa_column=Column(Numeric(18, 2), nullable=False),
    )
    revenue_capacity_value: float = Field(
        ge=0,
        sa_column=Column(Numeric(18, 2), nullable=False),
    )
    estimated_annual_cost: float = Field(
        ge=0,
        sa_column=Column(Numeric(18, 2), nullable=False),
    )
    time_to_impact_months: int = Field(default=0, ge=0, le=120)
    primary_kpi: str = Field(min_length=1, max_length=255)
    kpi_target: str = Field(min_length=1, max_length=255)
    confidence: str = Field(min_length=1, max_length=16, default="medium")
    currency: str = Field(min_length=3, max_length=3, default="EUR")
    calculation_version: str = Field(min_length=1, max_length=32)
    annual_time_value: float = Field(sa_column=Column(Numeric(18, 2), nullable=False))
    error_avoidance_value: float = Field(sa_column=Column(Numeric(18, 2), nullable=False))
    gross_value: float = Field(sa_column=Column(Numeric(18, 2), nullable=False))
    net_annual_value: float = Field(sa_column=Column(Numeric(18, 2), nullable=False))
    npv_3y: float = Field(sa_column=Column(Numeric(18, 2), nullable=False))
    payback_months: float | None = Field(default=None, sa_column=Column(Numeric(10, 2)))
    input_snapshot_json: dict[str, Any] = Field(
        sa_column=Column("input_snapshot_json", JSON, nullable=False),
    )
    source_snapshot_json: dict[str, Any] = Field(
        sa_column=Column("source_snapshot_json", JSON, nullable=False),
    )
    scenarios_json: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))
    sensitivities_json: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))


class ValueAssessment(
    ValueAssessmentBase,
    UUIDPrimaryKeyModel,
    TimestampedModel,
    table=True,
):
    __tablename__ = "value_assessments"
    __table_args__ = (
        UniqueConstraint(
            "assessment_version_id",
            "revision",
            name="uq_value_assessment_assessment_version",
        ),
    )

    created_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id",
        nullable=False,
        index=True,
    )


class ScoreConfigurationVersionBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    version: int = Field(ge=1)
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, default=True),
    )
    weights_json: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    thresholds_json: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))


class ScoreConfigurationVersion(
    ScoreConfigurationVersionBase,
    UUIDPrimaryKeyModel,
    TimestampedModel,
    table=True,
):
    __tablename__ = "score_configuration_versions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "version",
            name="uq_score_configuration_workspace_version",
        ),
    )

    created_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id",
        nullable=False,
        index=True,
    )


class ScorecardVersionBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    use_case_id: uuid.UUID = Field(foreign_key="use_cases.id", nullable=False, index=True)
    assessment_version_id: uuid.UUID = Field(
        foreign_key="assessment_versions.id",
        nullable=False,
        index=True,
    )
    value_assessment_id: uuid.UUID = Field(
        foreign_key="value_assessments.id",
        nullable=False,
        index=True,
    )
    score_configuration_version_id: uuid.UUID = Field(
        foreign_key="score_configuration_versions.id",
        nullable=False,
        index=True,
    )
    version: int = Field(ge=1)
    priority_score: float = Field(sa_column=Column(Numeric(8, 3), nullable=False))
    readiness_average: float = Field(sa_column=Column(Numeric(8, 3), nullable=False))
    category: str = Field(min_length=1, max_length=64)
    risk_profile: str = Field(min_length=1, max_length=16)
    confidence_level: str = Field(min_length=1, max_length=16)
    calculation_version: str = Field(min_length=1, max_length=32)
    manual_override: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )
    override_reason: str | None = Field(default=None, max_length=2000)
    input_snapshot_json: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    formula_snapshot_json: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))


class ScorecardVersion(
    ScorecardVersionBase,
    UUIDPrimaryKeyModel,
    TimestampedModel,
    table=True,
):
    __tablename__ = "scorecard_versions"
    __table_args__ = (
        UniqueConstraint(
            "use_case_id",
            "version",
            name="uq_scorecard_use_case_version",
        ),
    )

    created_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id",
        nullable=False,
        index=True,
    )


class DimensionScoreRecordBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    scorecard_version_id: uuid.UUID = Field(
        foreign_key="scorecard_versions.id",
        nullable=False,
        index=True,
    )
    dimension: ScoreDimension = Field(max_length=64)
    weight: float = Field(sa_column=Column(Numeric(8, 4), nullable=False))
    score: int = Field(ge=1, le=5)
    source: str = Field(min_length=1, max_length=255)
    justification: str = Field(min_length=1, max_length=2000)
    confidence: str = Field(min_length=1, max_length=16)
    is_manual_override: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )
    override_reason: str | None = Field(default=None, max_length=2000)


class DimensionScoreRecord(
    DimensionScoreRecordBase,
    UUIDPrimaryKeyModel,
    TimestampedModel,
    table=True,
):
    __tablename__ = "dimension_scores"
    __table_args__ = (
        UniqueConstraint(
            "scorecard_version_id",
            "dimension",
            name="uq_dimension_score_scorecard_dimension",
        ),
    )

    created_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id",
        nullable=False,
        index=True,
    )


class DocumentBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    use_case_id: uuid.UUID = Field(foreign_key="use_cases.id", nullable=False, index=True)
    type: DocumentType = Field(max_length=64)
    language: str = Field(min_length=2, max_length=16, default="fr")
    status: DocumentStatus = Field(default=DocumentStatus.DRAFT, max_length=32)
    current_version_no: int | None = Field(default=None, ge=1)


class Document(DocumentBase, UUIDPrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "use_case_id",
            "type",
            "language",
            name="uq_document_use_case_type_language",
        ),
    )

    created_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id",
        nullable=False,
        index=True,
    )


class DocumentVersionBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    document_id: uuid.UUID = Field(foreign_key="documents.id", nullable=False, index=True)
    version_no: int = Field(ge=1)
    format: DocumentFormat = Field(max_length=16)
    storage_key: str = Field(min_length=1, max_length=1024)
    sha256: str = Field(min_length=64, max_length=64)
    file_size_bytes: int = Field(ge=1)
    source_assessment_version_id: uuid.UUID = Field(
        foreign_key="assessment_versions.id",
        nullable=False,
        index=True,
    )
    source_assessment_version_no: int = Field(ge=1)
    source_scorecard_version_id: uuid.UUID = Field(
        foreign_key="scorecard_versions.id",
        nullable=False,
        index=True,
    )
    source_scorecard_version_no: int = Field(ge=1)
    source_review_id: uuid.UUID = Field(foreign_key="reviews.id", nullable=False, index=True)
    source_review_status: ReviewStatus = Field(max_length=32)
    source_snapshot_json: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    ai_assisted_sections_json: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))
    idempotency_key: str = Field(min_length=1, max_length=255)
    response_snapshot_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    approved_by_subject_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="identity_subjects.id",
        index=True,
    )
    approved_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class DocumentVersion(
    DocumentVersionBase,
    UUIDPrimaryKeyModel,
    TimestampedModel,
    table=True,
):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "version_no",
            "format",
            name="uq_document_version_document_version_format",
        ),
        UniqueConstraint(
            "created_by_subject_id",
            "idempotency_key",
            name="uq_document_version_actor_idempotency_key",
        ),
    )

    created_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id",
        nullable=False,
        index=True,
    )
