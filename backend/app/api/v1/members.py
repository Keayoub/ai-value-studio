from __future__ import annotations

import uuid
from typing import Annotated

from app.api.v1.errors import AppError
from app.audit.service import AuditService
from app.db.models.identity import IdentitySubject
from app.db.models.workspace import WorkspaceMembership
from app.db.session import (
    get_session,
    set_postgres_actor,
    set_postgres_workspace,
    set_postgres_workspace_verified,
)
from app.schemas.common import CursorPageResponse
from app.schemas.workspace import (
    WorkspaceMemberCreateRequest,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdateRequest,
)
from app.security.auth import AuthContext, get_auth_context
from app.security.roles import Permission, ProductRole
from app.security.tenancy import (
    ScopedRepository,
    ensure_workspace_permission,
    resolve_workspace_context,
)
from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session, select

router = APIRouter(tags=["members"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[Session, Depends(get_session)]


def _serialize_member(
    membership: WorkspaceMembership, identity: IdentitySubject
) -> WorkspaceMemberResponse:
    return WorkspaceMemberResponse(
        membership_id=membership.id,
        workspace_id=membership.workspace_id,
        role=membership.role,
        status=membership.status,
        created_at=membership.created_at,
        updated_at=membership.updated_at,
        identity={
            "id": str(identity.id),
            "subject": identity.subject,
            "issuer": identity.issuer,
            "tenant_id": identity.tenant_id,
            "oid": identity.oid,
            "display_name": identity.display_name,
            "email": identity.email,
        },
    )


def _resolve_or_create_identity(
    session: Session, payload: WorkspaceMemberCreateRequest
) -> IdentitySubject:
    subject_value = payload.identity.subject or (
        f"{payload.identity.issuer}|{payload.identity.tenant_id}|{payload.identity.oid}"
    )
    statement = select(IdentitySubject).where(
        IdentitySubject.issuer == payload.identity.issuer,
        IdentitySubject.tenant_id == payload.identity.tenant_id,
        IdentitySubject.oid == payload.identity.oid,
    )
    identity = session.exec(statement).first()
    if identity is None:
        identity = IdentitySubject(
            subject=subject_value,
            issuer=payload.identity.issuer,
            tenant_id=payload.identity.tenant_id,
            oid=payload.identity.oid,
            display_name=payload.identity.display_name,
            email=payload.identity.email,
        )
        session.add(identity)
        session.flush()
        return identity

    identity.display_name = payload.identity.display_name or identity.display_name
    identity.email = payload.identity.email or identity.email
    session.add(identity)
    session.flush()
    return identity


def _ensure_no_escalation(actor: AuthContext, target_role: ProductRole) -> None:
    if (
        target_role == ProductRole.WORKSPACE_ADMIN
        and ProductRole.WORKSPACE_ADMIN not in actor.token_roles
    ):
        raise AppError(
            status_code=403,
            title="Forbidden",
            detail="Only WorkspaceAdmin token holders may grant WorkspaceAdmin.",
        )


@router.get(
    "/workspaces/{workspace_id}/members", response_model=CursorPageResponse[WorkspaceMemberResponse]
)
def list_members(
    workspace_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> CursorPageResponse[WorkspaceMemberResponse]:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.MEMBERS_READ)
    rows, next_cursor = ScopedRepository(session, context).list_memberships(
        limit=limit, cursor=cursor
    )
    return CursorPageResponse(
        items=[_serialize_member(membership, identity) for membership, identity in rows],
        next_cursor=next_cursor,
    )


@router.post(
    "/workspaces/{workspace_id}/members", response_model=WorkspaceMemberResponse, status_code=201
)
def create_member(
    workspace_id: uuid.UUID,
    payload: WorkspaceMemberCreateRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> WorkspaceMemberResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.MEMBERS_MANAGE)
    target_role = payload.role
    _ensure_no_escalation(auth_context, target_role)

    identity = _resolve_or_create_identity(session, payload)
    existing_statement = select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == context.workspace.id,
        WorkspaceMembership.identity_subject_id == identity.id,
    )
    existing = session.exec(existing_statement).first()
    if existing is not None:
        raise AppError(
            status_code=409, title="Conflict", detail="Workspace membership already exists."
        )

    membership = WorkspaceMembership(
        workspace_id=context.workspace.id,
        identity_subject_id=identity.id,
        role=target_role.value,
        status=payload.status,
        created_by_subject_id=context.membership.identity_subject_id,
    )
    ScopedRepository(session, context).create_membership(membership)
    session.flush()

    AuditService(session).append(
        context=context,
        action="workspace_member.created",
        entity_type="workspace_membership",
        entity_id=str(membership.id),
        request_id=str(request.state.request_id),
        after={
            "role": membership.role,
            "status": membership.status,
            "identity_subject_id": str(identity.id),
        },
        metadata={
            "membership_role": membership.role,
            "membership_status": membership.status,
        },
    )
    refreshed_workspace_id = context.workspace.id
    session.commit()
    if context.actor.identity_subject_id is not None:
        set_postgres_actor(session, str(context.actor.identity_subject_id))
    set_postgres_workspace(session, str(refreshed_workspace_id))
    set_postgres_workspace_verified(session)
    session.refresh(membership)
    return _serialize_member(membership, identity)


@router.patch(
    "/workspaces/{workspace_id}/members/{membership_id}", response_model=WorkspaceMemberResponse
)
def update_member(
    workspace_id: uuid.UUID,
    membership_id: uuid.UUID,
    payload: WorkspaceMemberUpdateRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> WorkspaceMemberResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.MEMBERS_MANAGE)
    repository = ScopedRepository(session, context)
    row = repository.get_membership(membership_id)
    if row is None:
        raise AppError(status_code=404, title="Not Found", detail="Workspace membership not found.")

    membership, identity = row
    before = {"role": membership.role, "status": membership.status}
    changes = payload.model_dump(exclude_unset=True)
    if "role" in changes and changes["role"] is not None:
        target_role = changes["role"]
        _ensure_no_escalation(auth_context, target_role)
        membership.role = target_role.value
    if "status" in changes and changes["status"] is not None:
        membership.status = changes["status"]
    if "display_name" in changes:
        identity.display_name = changes["display_name"]
    if "email" in changes:
        identity.email = changes["email"]

    session.add(identity)
    session.add(membership)
    AuditService(session).append(
        context=context,
        action="workspace_member.updated",
        entity_type="workspace_membership",
        entity_id=str(membership.id),
        request_id=str(request.state.request_id),
        before=before,
        after={"role": membership.role, "status": membership.status},
        metadata={"changed_fields": sorted(changes)},
    )
    refreshed_workspace_id = context.workspace.id
    session.commit()
    if context.actor.identity_subject_id is not None:
        set_postgres_actor(session, str(context.actor.identity_subject_id))
    set_postgres_workspace(session, str(refreshed_workspace_id))
    set_postgres_workspace_verified(session)
    session.refresh(membership)
    session.refresh(identity)
    return _serialize_member(membership, identity)
