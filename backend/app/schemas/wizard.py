from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from app.db.models.lifecycle import AnswerSource, AssessmentStatus
from pydantic import BaseModel, ConfigDict, Field

JsonValue = Any


class AssessmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interview_mode: bool = False
    respondent_membership_id: uuid.UUID | None = None
    force_new_version: bool = False


class AnswerUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: JsonValue
    evidence_text: str | None = Field(default=None, max_length=2000)
    confidence: str | None = Field(default=None, max_length=120)
    captured_for_membership_id: uuid.UUID | None = None
    source: AnswerSource | None = None
    confirm_overwrite_ai_assisted: bool = False


class StepValidationError(BaseModel):
    question_key: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=300)


class StepValuePreview(BaseModel):
    annual_time_value: float
    error_avoidance_value: float
    gross_value: float
    net_value: float


class DerivedAssessmentState(BaseModel):
    step4_preview: StepValuePreview | None = None
    risk_profile: Literal["Low", "Medium", "High", "Critical"] | None = None
    missing_information: list[str] = Field(default_factory=list)
    sponsor_name: str | None = None


class StepValidationResponse(BaseModel):
    step: int = Field(ge=1, le=8)
    is_valid: bool
    errors: list[StepValidationError] = Field(default_factory=list)
    derived: DerivedAssessmentState


class WizardQuestionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    field_type: str
    label: str
    help_text: str | None = None
    placeholder: str | None = None
    options: list[dict[str, str]] = Field(default_factory=list)
    field_schema: dict[str, JsonValue] = Field(
        default_factory=dict,
        alias="schema",
        serialization_alias="schema",
    )
    step_index: int = Field(ge=0, le=8)
    required: bool
    visible: bool
    read_only: bool
    contributor_editable: bool
    value: JsonValue | None = None
    evidence_text: str | None = None
    confidence: str | None = None
    captured_for_membership_id: uuid.UUID | None = None
    source: AnswerSource | None = None
    updated_at: datetime | None = None


class WizardStepResponse(BaseModel):
    index: int = Field(ge=0, le=8)
    key: str
    title: str
    purpose: str
    available: bool
    optional: bool
    questions: list[WizardQuestionResponse]


class TemplateVersionResponse(BaseModel):
    id: uuid.UUID
    template_key: str
    version: int
    locale: str
    title: str
    description: str | None = None
    steps: list[WizardStepResponse]


class AssessmentSummaryResponse(BaseModel):
    id: uuid.UUID
    use_case_id: uuid.UUID
    workspace_id: uuid.UUID
    version: int
    status: AssessmentStatus
    interview_mode: bool
    respondent_membership_id: uuid.UUID | None = None
    created_by_subject_id: uuid.UUID
    submitted_by_subject_id: uuid.UUID | None = None
    submitted_at: datetime | None = None
    approved_by_subject_id: uuid.UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    can_edit: bool
    can_submit: bool
    editor_role: str


class HypothesisResponse(BaseModel):
    id: uuid.UUID
    statement: str
    kind: str
    status: str


class AssessmentEnvelopeResponse(BaseModel):
    assessment: AssessmentSummaryResponse
    template: TemplateVersionResponse
    derived: DerivedAssessmentState
    validation: list[StepValidationResponse] = Field(default_factory=list)
    hypotheses: list[HypothesisResponse] = Field(default_factory=list)


class AnswerResponse(BaseModel):
    question_key: str
    value: JsonValue
    evidence_text: str | None = None
    confidence: str | None = None
    captured_for_membership_id: uuid.UUID | None = None
    source: AnswerSource
    updated_at: datetime


class AssessmentSubmitResponse(BaseModel):
    submitted: AssessmentEnvelopeResponse
