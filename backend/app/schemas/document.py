from __future__ import annotations

import uuid
from datetime import datetime

from app.db.models.lifecycle import DocumentFormat, DocumentStatus, DocumentType, ReviewStatus
from pydantic import BaseModel, ConfigDict, Field


class DocumentGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: DocumentType
    format: DocumentFormat
    language: str = Field(default="fr", min_length=2, max_length=16)


class DocumentEligibilityResponse(BaseModel):
    can_generate_markdown: bool
    can_generate_pdf: bool
    markdown_reason: str | None = None
    pdf_reason: str | None = None
    source_assessment_version: int | None = None
    source_scorecard_version: int | None = None
    source_review_status: ReviewStatus | None = None


class DocumentVersionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    version_no: int
    format: DocumentFormat
    storage_key: str
    sha256: str
    file_size_bytes: int
    source_assessment_version_no: int
    source_scorecard_version_no: int
    source_review_id: uuid.UUID
    source_review_status: ReviewStatus
    ai_assisted_sections: list[dict[str, object]]
    approved_by_subject_id: uuid.UUID | None = None
    approved_at: datetime | None = None
    created_by_subject_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    metadata_diff: list[str] = Field(default_factory=list)


class DocumentResponse(BaseModel):
    id: uuid.UUID | None = None
    use_case_id: uuid.UUID
    type: DocumentType
    language: str
    status: DocumentStatus
    current_version_no: int | None = None
    current_version: DocumentVersionResponse | None = None
    versions: list[DocumentVersionResponse] = Field(default_factory=list)
    eligibility: DocumentEligibilityResponse


class DocumentDownloadMetadataResponse(BaseModel):
    filename: str
    version_id: uuid.UUID
    document_id: uuid.UUID
    sha256: str
    file_size_bytes: int
    content_type: str


class DocumentDownloadEnvelopeResponse(BaseModel):
    metadata: DocumentDownloadMetadataResponse
