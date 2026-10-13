from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from app.db.base import TimestampedModel, UUIDPrimaryKeyModel
from sqlalchemy import JSON, Boolean, Column, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel


class WorkspaceStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class WorkspaceSizeBand(StrEnum):
    MICRO = "micro"
    SMALL = "small"
    MID_MARKET = "mid-market"
    ENTERPRISE = "enterprise"
    PUBLIC_SECTOR = "public-sector"


class WorkspaceConfidentialityPolicy(StrEnum):
    STANDARD = "standard"
    INTERNAL_ONLY = "internal-only"
    RESTRICTED = "restricted"
    REGULATED = "regulated"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    DISABLED = "disabled"


class WorkspaceBase(SQLModel):
    name: str = Field(min_length=1, max_length=200, index=True)
    sector: str | None = Field(default=None, max_length=120)
    country_region: str | None = Field(default=None, max_length=120)
    size_band: WorkspaceSizeBand | None = Field(default=None, max_length=32)
    default_language: str = Field(default="en", min_length=2, max_length=16)
    description: str | None = Field(default=None, max_length=2000)
    branding_json: dict[str, str] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    confidentiality_policy: WorkspaceConfidentialityPolicy = Field(
        default=WorkspaceConfidentialityPolicy.INTERNAL_ONLY,
        max_length=32,
    )
    status: WorkspaceStatus = Field(default=WorkspaceStatus.ACTIVE)
    ai_assistance_enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )
    ai_assistance_consent_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )
    ai_assistance_consent_by_subject_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="identity_subjects.id",
        nullable=True,
        index=True,
    )
    ai_assistance_data_processing_note: str | None = Field(default=None, max_length=2000)


class Workspace(WorkspaceBase, UUIDPrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "workspaces"
    created_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id", nullable=False, index=True
    )


class WorkspaceMembershipBase(SQLModel):
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    identity_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id",
        nullable=False,
        index=True,
    )
    role: str = Field(min_length=1, max_length=64)
    status: MembershipStatus = Field(default=MembershipStatus.ACTIVE)


class WorkspaceMembership(
    WorkspaceMembershipBase,
    UUIDPrimaryKeyModel,
    TimestampedModel,
    table=True,
):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "identity_subject_id",
            name="uq_workspace_membership_workspace_subject",
        ),
    )
    created_by_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id", nullable=False, index=True
    )
