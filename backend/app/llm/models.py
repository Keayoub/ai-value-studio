from __future__ import annotations

import uuid
from datetime import datetime

from app.db.base import TimestampedModel, UUIDPrimaryKeyModel
from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel


class LlmRateLimitBucket(SQLModel, UUIDPrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "llm_rate_limit_buckets"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "actor_subject_id",
            "bucket_start",
            name="uq_llm_rate_limit_workspace_actor_bucket",
        ),
    )

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    actor_subject_id: uuid.UUID = Field(
        foreign_key="identity_subjects.id",
        nullable=False,
        index=True,
    )
    bucket_start: datetime = Field(sa_type=DateTime(timezone=True), nullable=False, index=True)
    request_count: int = Field(default=0, ge=0)


class LlmCircuitBreaker(SQLModel, UUIDPrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "llm_circuit_breakers"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "provider",
            name="uq_llm_circuit_workspace_provider",
        ),
    )

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False, index=True)
    provider: str = Field(min_length=1, max_length=64, index=True)
    consecutive_failures: int = Field(default=0, ge=0)
    opened_until: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    last_failure_code: str | None = Field(default=None, max_length=120)
    last_failure_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
