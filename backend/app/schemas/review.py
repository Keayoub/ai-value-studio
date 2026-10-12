from __future__ import annotations

import uuid
from datetime import datetime

from app.db.models.lifecycle import ApprovalDecision, ReviewRecommendation, ReviewStatus
from pydantic import BaseModel, ConfigDict, Field


class ReviewActorResponse(BaseModel):
    subject_id: uuid.UUID
    display_name: str | None = None
    role: str | None = None


class ReviewCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: ReviewRecommendation
    summary: str = Field(min_length=1, max_length=4000)
    risks: list[str] = Field(default_factory=list, max_length=20)


class ReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_reason: str | None = Field(default=None, max_length=4000)


class ReviewCommentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=4000)
    parent_comment_id: uuid.UUID | None = None


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    review_id: uuid.UUID
    use_case_id: uuid.UUID
    decision: ApprovalDecision
    decision_reason: str
    approver: ReviewActorResponse
    decided_at: datetime
    idempotency_key: str


class ReviewResponse(BaseModel):
    id: uuid.UUID
    use_case_id: uuid.UUID
    assessment_version_id: uuid.UUID
    assessment_version: int
    status: ReviewStatus
    recommendation: ReviewRecommendation
    summary: str
    risks: list[str]
    submitted_by: ReviewActorResponse
    submitted_at: datetime
    decided_by: ReviewActorResponse | None = None
    decided_at: datetime | None = None
    decision_reason: str | None = None
    approval: ApprovalResponse | None = None


class ReviewCommentResponse(BaseModel):
    id: uuid.UUID
    review_id: uuid.UUID
    use_case_id: uuid.UUID
    parent_comment_id: uuid.UUID | None = None
    body: str
    author: ReviewActorResponse
    created_at: datetime


class ReviewStateResponse(BaseModel):
    review: ReviewResponse | None = None
    review_history: list[ReviewResponse] = Field(default_factory=list)
    comments: list[ReviewCommentResponse] = Field(default_factory=list)
    can_submit_review: bool
    can_comment: bool
    can_decide: bool
    can_create_new_draft: bool


class ReviewInboxItemResponse(BaseModel):
    review_id: uuid.UUID
    use_case_id: uuid.UUID
    program_id: uuid.UUID
    use_case_title: str
    program_name: str
    assessment_version: int
    status: ReviewStatus
    recommendation: ReviewRecommendation
    submitted_at: datetime
    submitted_by: ReviewActorResponse
    decision_reason: str | None = None
