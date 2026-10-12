from __future__ import annotations

import uuid

from app.security.roles import ProductRole
from pydantic import BaseModel, Field


class IdentitySubjectResponse(BaseModel):
    id: uuid.UUID
    subject: str
    issuer: str
    tenant_id: str
    oid: str
    display_name: str | None = None
    email: str | None = None


class MyMembershipResponse(BaseModel):
    membership_id: uuid.UUID
    workspace_id: uuid.UUID
    workspace_name: str
    role: str
    status: str
    permissions: list[str]


class MeResponse(BaseModel):
    subject: str
    issuer: str
    tenant_id: str
    oid: str
    display_name: str | None = None
    email: str | None = None
    token_roles: list[str]
    permitted_workspace_ids: list[uuid.UUID]
    memberships: list[MyMembershipResponse]


class DevIdentityRequest(BaseModel):
    subject_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=255)
    role: ProductRole


class DevIdentityResponse(BaseModel):
    subject: str
    issuer: str
    tenant_id: str
    oid: str
    display_name: str
    role: ProductRole
    headers: dict[str, str]
