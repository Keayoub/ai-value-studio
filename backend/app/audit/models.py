from __future__ import annotations

import uuid
from datetime import datetime

from app.db.base import UUIDPrimaryKeyModel, utc_now
from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel


class AuditEvent(SQLModel, UUIDPrimaryKeyModel, table=True):
    __tablename__ = "audit_events"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    actor_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id", nullable=False, index=True
    )
    action: str = Field(min_length=1, max_length=200)
    entity_type: str = Field(min_length=1, max_length=120)
    entity_id: str = Field(min_length=1, max_length=120)
    request_id: str = Field(min_length=1, max_length=120, index=True)
    occurred_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=utc_now),
    )
    before_hash: str | None = Field(default=None, max_length=64)
    after_hash: str | None = Field(default=None, max_length=64)
    metadata_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    ip_hash: str | None = Field(default=None, max_length=128)
