from __future__ import annotations

import uuid
from datetime import date, datetime

from app.db.models.lifecycle import (
    ProgramAssignmentRole,
    ProgramConfidentialityLevel,
    ProgramStatus,
    UseCaseStatus,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProgramCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    strategic_objective: str | None = Field(default=None, max_length=2000)
    departments: list[str] | None = Field(default=None, max_length=20)
    period_start: date | None = None
    period_end: date | None = None
    sponsor_membership_id: uuid.UUID | None = None
    consultant_membership_id: uuid.UUID | None = None
    target_use_case_count: int | None = Field(default=None, ge=0, le=5000)
    questionnaire_template_version_id: uuid.UUID | None = None
    confidentiality_level: ProgramConfidentialityLevel = (
        ProgramConfidentialityLevel.INTERNAL_ONLY
    )

    @model_validator(mode="after")
    def validate_period(self) -> ProgramCreateRequest:
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValueError("Program end date must be on or after the start date.")
        return self


class ProgramUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    strategic_objective: str | None = Field(default=None, max_length=2000)
    departments: list[str] | None = Field(default=None, max_length=20)
    period_start: date | None = None
    period_end: date | None = None
    sponsor_membership_id: uuid.UUID | None = None
    consultant_membership_id: uuid.UUID | None = None
    target_use_case_count: int | None = Field(default=None, ge=0, le=5000)
    questionnaire_template_version_id: uuid.UUID | None = None
    confidentiality_level: ProgramConfidentialityLevel | None = None

    @model_validator(mode="after")
    def validate_period(self) -> ProgramUpdateRequest:
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValueError("Program end date must be on or after the start date.")
        return self


class ProgramMemberCreateRequest(BaseModel):
    membership_id: uuid.UUID
    assignment_role: ProgramAssignmentRole


class ProgramStatusTransitionRequest(BaseModel):
    target_status: ProgramStatus


class ProgramResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    strategic_objective: str | None = None
    departments: list[str]
    period_start: date | None = None
    period_end: date | None = None
    sponsor_membership_id: uuid.UUID | None = None
    consultant_membership_id: uuid.UUID | None = None
    target_use_case_count: int | None = None
    questionnaire_template_version_id: uuid.UUID | None = None
    confidentiality_level: ProgramConfidentialityLevel
    status: ProgramStatus
    created_by_subject_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProgramMemberResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    program_id: uuid.UUID
    membership_id: uuid.UUID
    assignment_role: ProgramAssignmentRole
    created_by_subject_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class UseCaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    owner_membership_id: uuid.UUID | None = None
    recommendation: str | None = Field(default=None, max_length=120)


class UseCaseUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    owner_membership_id: uuid.UUID | None = None
    recommendation: str | None = Field(default=None, max_length=120)


class UseCaseStatusTransitionRequest(BaseModel):
    target_status: UseCaseStatus


class UseCaseResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    program_id: uuid.UUID
    title: str
    department: str | None = None
    owner_membership_id: uuid.UUID | None = None
    status: UseCaseStatus
    recommendation: str | None = None
    category: str | None = None
    priority_score: float | None = None
    score_version: int | None = None
    confidence_level: str | None = None
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    current_assessment_version: int | None = None
    created_by_subject_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
