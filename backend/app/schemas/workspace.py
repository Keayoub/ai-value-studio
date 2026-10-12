from __future__ import annotations

import uuid
from datetime import datetime

from app.db.models.workspace import (
    MembershipStatus,
    WorkspaceConfidentialityPolicy,
    WorkspaceSizeBand,
    WorkspaceStatus,
)
from app.security.roles import ProductRole
from pydantic import BaseModel, ConfigDict, Field, field_validator


class WorkspaceBranding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_url: str | None = Field(default=None, max_length=500)
    wordmark: str | None = Field(default=None, max_length=120)


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sector: str | None = Field(default=None, max_length=120)
    country_region: str | None = Field(default=None, max_length=120)
    size_band: WorkspaceSizeBand | None = None
    default_language: str = Field(default="en", min_length=2, max_length=16)
    description: str | None = Field(default=None, max_length=2000)
    branding_json: WorkspaceBranding | None = None
    confidentiality_policy: WorkspaceConfidentialityPolicy = (
        WorkspaceConfidentialityPolicy.INTERNAL_ONLY
    )

    @field_validator("default_language")
    @classmethod
    def validate_default_language(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Default language is required.")
        if not all(part.isalpha() for part in normalized.split("-")):
            raise ValueError("Default language must be a short language tag like en or fr-FR.")
        return normalized


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sector: str | None = Field(default=None, max_length=120)
    country_region: str | None = Field(default=None, max_length=120)
    size_band: WorkspaceSizeBand | None = None
    default_language: str | None = Field(default=None, min_length=2, max_length=16)
    description: str | None = Field(default=None, max_length=2000)
    branding_json: WorkspaceBranding | None = None
    confidentiality_policy: WorkspaceConfidentialityPolicy | None = None
    status: WorkspaceStatus | None = None
    ai_assistance_enabled: bool | None = None
    ai_assistance_data_processing_note: str | None = Field(default=None, max_length=2000)

    @field_validator("default_language")
    @classmethod
    def validate_optional_default_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Default language cannot be blank.")
        if not all(part.isalpha() for part in normalized.split("-")):
            raise ValueError("Default language must be a short language tag like en or fr-FR.")
        return normalized


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    sector: str | None = None
    country_region: str | None = None
    size_band: WorkspaceSizeBand | None = None
    default_language: str
    description: str | None = None
    branding_json: WorkspaceBranding | None = None
    confidentiality_policy: WorkspaceConfidentialityPolicy
    status: WorkspaceStatus
    ai_assistance_enabled: bool
    ai_assistance_available: bool
    ai_assistance_consent_at: datetime | None = None
    ai_assistance_consent_by_subject_id: uuid.UUID | None = None
    ai_assistance_data_processing_note: str | None = None
    created_by_subject_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    my_role: str
    my_membership_status: str


class IdentityProvisionRequest(BaseModel):
    issuer: str = Field(min_length=1, max_length=255)
    tenant_id: str = Field(min_length=1, max_length=255)
    oid: str = Field(min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    subject: str | None = Field(default=None, max_length=255)


class WorkspaceMemberCreateRequest(BaseModel):
    identity: IdentityProvisionRequest
    role: ProductRole
    status: MembershipStatus = MembershipStatus.ACTIVE


class WorkspaceMemberUpdateRequest(BaseModel):
    role: ProductRole | None = None
    status: MembershipStatus | None = None
    display_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)


class WorkspaceMemberResponse(BaseModel):
    membership_id: uuid.UUID
    workspace_id: uuid.UUID
    role: str
    status: MembershipStatus
    created_at: datetime
    updated_at: datetime
    identity: dict
