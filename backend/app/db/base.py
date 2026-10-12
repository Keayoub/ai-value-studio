from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlmodel import Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampedModel:
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"nullable": False, "default": utc_now},
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"nullable": False, "default": utc_now, "onupdate": utc_now},
    )


class UUIDPrimaryKeyModel:
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, nullable=False)


def load_metadata() -> None:
    from app.audit import models as _audit_models  # noqa: F401
    from app.db.models import identity as _identity_models  # noqa: F401
    from app.db.models import lifecycle as _lifecycle_models  # noqa: F401
    from app.db.models import workspace as _workspace_models  # noqa: F401
