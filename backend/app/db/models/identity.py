from __future__ import annotations

import uuid

from app.db.base import TimestampedModel, UUIDPrimaryKeyModel
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class IdentitySubjectBase(SQLModel):
    subject: str = Field(index=True, unique=True, max_length=255)
    issuer: str = Field(index=True, max_length=255)
    tenant_id: str = Field(index=True, max_length=255)
    oid: str = Field(index=True, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)


class IdentitySubject(IdentitySubjectBase, UUIDPrimaryKeyModel, TimestampedModel, table=True):
    __tablename__ = "identity_subjects"
    __table_args__ = (
        UniqueConstraint("issuer", "tenant_id", "oid", name="uq_identity_subject_issuer_tid_oid"),
    )


class IdentityReference(SQLModel):
    id: uuid.UUID
    subject: str
    issuer: str
    tenant_id: str
    oid: str
    display_name: str | None = None
    email: str | None = None
