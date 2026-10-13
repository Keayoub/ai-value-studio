from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from app.api.v1.errors import AppError
from app.audit.service import AuditService
from app.db.models.identity import IdentitySubject
from app.db.models.workspace import MembershipStatus, Workspace, WorkspaceMembership
from app.db.session import (
    get_session,
    set_postgres_actor,
    set_postgres_workspace,
    set_postgres_workspace_create_allowed,
    set_postgres_workspace_verified,
)
from app.llm.service import llm_provider_is_configured
from app.schemas.common import CursorPageResponse
from app.schemas.workspace import (
    WorkspaceCreateRequest,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)
from app.security.auth import AuthContext, get_auth_context
from app.security.roles import Permission, ProductRole, has_elevated_workspace_role
from app.security.tenancy import (
    ensure_workspace_permission,
    list_actor_workspaces,
    resolve_workspace_context,
)
from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session, select

router = APIRouter(tags=["workspaces"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[Session, Depends(get_session)]


def _serialize_workspace(
    workspace: Workspace, membership: WorkspaceMembership
) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        sector=workspace.sector,
        country_region=workspace.country_region,
        size_band=workspace.size_band,
        default_language=workspace.default_language,
        description=workspace.description,
        branding_json=workspace.branding_json,
        confidentiality_policy=workspace.confidentiality_policy,
        status=workspace.status,
        ai_assistance_enabled=workspace.ai_assistance_enabled,
        ai_assistance_available=llm_provider_is_configured(),
        ai_assistance_consent_at=workspace.ai_assistance_consent_at,
        ai_assistance_consent_by_subject_id=workspace.ai_assistance_consent_by_subject_id,
        ai_assistance_data_processing_note=workspace.ai_assistance_data_processing_note,
        created_by_subject_id=workspace.created_by_subject_id,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        my_role=membership.role,
        my_membership_status=membership.status,
    )


def _resolve_or_create_subject(session: Session, auth_context: AuthContext) -> IdentitySubject:
    statement = select(IdentitySubject).where(
        IdentitySubject.issuer == auth_context.issuer,
        IdentitySubject.tenant_id == auth_context.tenant_id,
        IdentitySubject.oid == auth_context.oid,
    )
    subject = session.exec(statement).first()
    if subject is None:
        subject = IdentitySubject(
            subject=auth_context.subject,
            issuer=auth_context.issuer,
            tenant_id=auth_context.tenant_id,
            oid=auth_context.oid,
            display_name=auth_context.display_name,
            email=auth_context.email,
        )
        session.add(subject)
        session.flush()
    else:
        subject.display_name = auth_context.display_name
        subject.email = auth_context.email
        session.add(subject)
        session.flush()
    auth_context.identity_subject_id = subject.id
    return subject


@router.get("/workspaces", response_model=CursorPageResponse[WorkspaceResponse])
def list_workspaces(
    auth_context: AuthContextDependency,
    session: SessionDependency,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> CursorPageResponse[WorkspaceResponse]:
    rows, next_cursor = list_actor_workspaces(session, auth_context, cursor=cursor, limit=limit)
    items = [_serialize_workspace(workspace, membership) for membership, workspace in rows]
    return CursorPageResponse(items=items, next_cursor=next_cursor)


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
def create_workspace(
    payload: WorkspaceCreateRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> WorkspaceResponse:
    if not has_elevated_workspace_role(auth_context.token_roles):
        raise AppError(
            status_code=403,
            title="Forbidden",
            detail="Workspace creation requires Consultant or WorkspaceAdmin.",
        )

    actor_subject = _resolve_or_create_subject(session, auth_context)
    set_postgres_actor(session, str(actor_subject.id))

    workspace_id = uuid.uuid4()
    set_postgres_workspace(session, str(workspace_id))
    set_postgres_workspace_create_allowed(session)

    workspace = Workspace(
        id=workspace_id,
        name=payload.name,
        sector=payload.sector,
        country_region=payload.country_region,
        size_band=payload.size_band,
        default_language=payload.default_language,
        description=payload.description,
        branding_json=(
            payload.branding_json.model_dump(mode="json")
            if payload.branding_json is not None
            else None
        ),
        confidentiality_policy=payload.confidentiality_policy,
        created_by_subject_id=actor_subject.id,
    )
    session.add(workspace)
    session.flush()

    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        identity_subject_id=actor_subject.id,
        role=ProductRole.WORKSPACE_ADMIN.value,
        status=MembershipStatus.ACTIVE,
        created_by_subject_id=actor_subject.id,
    )
    set_postgres_workspace_verified(session)
    session.add(membership)
    session.flush()
    context = resolve_workspace_context(session, auth_context, workspace.id)
    AuditService(session).append(
        context=context,
        action="workspace.created",
        entity_type="workspace",
        entity_id=str(workspace.id),
        request_id=str(request.state.request_id),
        after={"name": workspace.name, "status": workspace.status},
        metadata={"created_by_membership_role": membership.role},
    )
    created_workspace_id = workspace_id
    session.commit()
    set_postgres_actor(session, str(actor_subject.id))
    set_postgres_workspace(session, str(created_workspace_id))
    set_postgres_workspace_verified(session)
    session.refresh(workspace)
    session.refresh(membership)
    return _serialize_workspace(workspace, membership)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(
    workspace_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> WorkspaceResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    return _serialize_workspace(context.workspace, context.membership)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(
    workspace_id: uuid.UUID,
    payload: WorkspaceUpdateRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> WorkspaceResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.WORKSPACE_UPDATE)

    before = {
        "name": context.workspace.name,
        "description": context.workspace.description,
        "status": context.workspace.status,
        "ai_assistance_enabled": context.workspace.ai_assistance_enabled,
        "ai_assistance_data_processing_note": context.workspace.ai_assistance_data_processing_note,
    }
    changes = payload.model_dump(exclude_unset=True)
    ai_enabled_changed = "ai_assistance_enabled" in changes
    ai_note_changed = "ai_assistance_data_processing_note" in changes
    if ai_enabled_changed or ai_note_changed:
        if context.membership.role != ProductRole.WORKSPACE_ADMIN.value:
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail="Only a workspace administrator can change AI assistance settings.",
            )
        next_enabled = changes.get("ai_assistance_enabled", context.workspace.ai_assistance_enabled)
        next_note = changes.get(
            "ai_assistance_data_processing_note",
            context.workspace.ai_assistance_data_processing_note,
        )
        if next_enabled and not (next_note or "").strip():
            raise AppError(
                status_code=422,
                title="Validation Error",
                detail=(
                    "Enabling AI assistance requires a data-processing note describing the "
                    "approved business summary shared with the provider."
                ),
            )
        if next_enabled and not context.workspace.ai_assistance_enabled:
            if context.actor.identity_subject_id is None:
                raise AppError(status_code=401, title="Unauthorized", detail="Identity missing.")
            context.workspace.ai_assistance_consent_at = datetime.now(UTC)
            context.workspace.ai_assistance_consent_by_subject_id = (
                context.actor.identity_subject_id
            )
    for key, value in changes.items():
        setattr(context.workspace, key, value)

    session.add(context.workspace)
    AuditService(session).append(
        context=context,
        action="workspace.updated",
        entity_type="workspace",
        entity_id=str(context.workspace.id),
        request_id=str(request.state.request_id),
        before=before,
        after={
            "name": context.workspace.name,
            "description": context.workspace.description,
            "status": context.workspace.status,
            "ai_assistance_enabled": context.workspace.ai_assistance_enabled,
            "ai_assistance_data_processing_note": (
                context.workspace.ai_assistance_data_processing_note
            ),
        },
        metadata={"changed_fields": sorted(changes)},
    )
    refreshed_workspace_id = context.workspace.id
    session.commit()
    if context.actor.identity_subject_id is not None:
        set_postgres_actor(session, str(context.actor.identity_subject_id))
    set_postgres_workspace(session, str(refreshed_workspace_id))
    set_postgres_workspace_verified(session)
    session.refresh(context.workspace)
    return _serialize_workspace(context.workspace, context.membership)
