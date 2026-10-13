from __future__ import annotations

import uuid
from typing import Annotated

from app.api.v1.errors import AppError
from app.audit.service import AuditService
from app.db.models.lifecycle import UseCase, UseCaseStatus
from app.db.session import (
    get_session,
    set_postgres_actor,
    set_postgres_workspace,
    set_postgres_workspace_verified,
)
from app.schemas.common import CursorPageResponse
from app.schemas.lifecycle import (
    UseCaseCreateRequest,
    UseCaseResponse,
    UseCaseStatusTransitionRequest,
    UseCaseUpdateRequest,
)
from app.security.auth import AuthContext, get_auth_context
from app.security.roles import Permission, ProductRole
from app.security.tenancy import (
    ScopedRepository,
    ensure_workspace_permission,
    resolve_workspace_context,
)
from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

router = APIRouter(tags=["use-cases"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[Session, Depends(get_session)]

USE_CASE_TRANSITIONS: dict[UseCaseStatus, set[UseCaseStatus]] = {
    UseCaseStatus.DRAFT: {UseCaseStatus.IN_PROGRESS},
    UseCaseStatus.IN_PROGRESS: set(),
    UseCaseStatus.SUBMITTED: set(),
    UseCaseStatus.CHANGES_REQUESTED: set(),
    UseCaseStatus.APPROVED: set(),
    UseCaseStatus.REJECTED: set(),
}

USE_CASE_TRANSITION_TARGETS_BY_ROLE: dict[ProductRole, set[UseCaseStatus]] = {
    ProductRole.CONSULTANT: {UseCaseStatus.IN_PROGRESS},
    ProductRole.WORKSPACE_ADMIN: {UseCaseStatus.IN_PROGRESS},
}


def _serialize_use_case(use_case: UseCase) -> UseCaseResponse:
    return UseCaseResponse(
        id=use_case.id,
        workspace_id=use_case.workspace_id,
        program_id=use_case.program_id,
        title=use_case.title,
        department=use_case.department,
        owner_membership_id=use_case.owner_membership_id,
        status=use_case.status,
        recommendation=use_case.recommendation,
        category=use_case.category,
        priority_score=(
            float(use_case.priority_score) if use_case.priority_score is not None else None
        ),
        score_version=use_case.score_version,
        confidence_level=use_case.confidence_level,
        submitted_at=use_case.submitted_at,
        approved_at=use_case.approved_at,
        current_assessment_version=use_case.current_assessment_version,
        created_by_subject_id=use_case.created_by_subject_id,
        created_at=use_case.created_at,
        updated_at=use_case.updated_at,
    )


def _refresh_session_scope(session: Session, context) -> None:
    if context.actor.identity_subject_id is not None:
        set_postgres_actor(session, str(context.actor.identity_subject_id))
    set_postgres_workspace(session, str(context.workspace.id))
    set_postgres_workspace_verified(session)


def _ensure_transition_authorized(
    context,
    payload: UseCaseStatusTransitionRequest,
) -> None:
    membership_role = ProductRole(context.membership.role)
    allowed_targets = USE_CASE_TRANSITION_TARGETS_BY_ROLE.get(membership_role, set())
    if payload.target_status not in allowed_targets:
        raise AppError(
            status_code=403,
            title="Forbidden",
            detail="This role cannot perform the requested use-case transition.",
        )


@router.get(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases",
    response_model=CursorPageResponse[UseCaseResponse],
)
def list_use_cases(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> CursorPageResponse[UseCaseResponse]:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_READ)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    rows, next_cursor = repository.list_use_cases(program, limit=limit, cursor=cursor)
    return CursorPageResponse(
        items=[_serialize_use_case(use_case) for use_case in rows],
        next_cursor=next_cursor,
    )


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases",
    response_model=UseCaseResponse,
    status_code=201,
)
def create_use_case(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    payload: UseCaseCreateRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> UseCaseResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_CREATE)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    owner_membership = (
        repository.resolve_workspace_membership(payload.owner_membership_id)
        if payload.owner_membership_id is not None
        else None
    )
    if payload.owner_membership_id is not None and owner_membership is None:
        raise AppError(
            status_code=404,
            title="Not Found",
            detail="Use-case owner membership not found in this workspace.",
        )

    use_case = UseCase(
        workspace_id=context.workspace.id,
        program_id=program.id,
        title=payload.title,
        department=payload.department,
        owner_membership_id=owner_membership.id if owner_membership is not None else None,
        recommendation=payload.recommendation,
        created_by_subject_id=context.membership.identity_subject_id,
    )
    repository.create_use_case(use_case)
    session.flush()

    AuditService(session).append(
        context=context,
        action="use_case.created",
        entity_type="use_case",
        entity_id=str(use_case.id),
        request_id=str(request.state.request_id),
        after={"title": use_case.title, "status": use_case.status},
        metadata={"program_id": str(program.id)},
    )
    session.commit()
    _refresh_session_scope(session, context)
    session.refresh(use_case)
    return _serialize_use_case(use_case)


@router.get(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}",
    response_model=UseCaseResponse,
)
def get_use_case(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> UseCaseResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_READ)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    use_case = repository.get_use_case(program, use_case_id)
    if use_case is None:
        raise AppError(status_code=404, title="Not Found", detail="Use case not found.")
    return _serialize_use_case(use_case)


@router.patch(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}",
    response_model=UseCaseResponse,
)
def update_use_case(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    payload: UseCaseUpdateRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> UseCaseResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_UPDATE)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    use_case = repository.get_use_case(program, use_case_id)
    if use_case is None:
        raise AppError(status_code=404, title="Not Found", detail="Use case not found.")

    before = {
        "title": use_case.title,
        "status": use_case.status,
        "owner_membership_id": str(use_case.owner_membership_id)
        if use_case.owner_membership_id
        else None,
    }
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes:
        use_case.title = changes["title"]
    if "department" in changes:
        use_case.department = changes["department"]
    if "owner_membership_id" in changes:
        owner_membership = (
            repository.resolve_workspace_membership(changes["owner_membership_id"])
            if changes["owner_membership_id"] is not None
            else None
        )
        if changes["owner_membership_id"] is not None and owner_membership is None:
            raise AppError(
                status_code=404,
                title="Not Found",
                detail="Use-case owner membership not found in this workspace.",
            )
        use_case.owner_membership_id = owner_membership.id if owner_membership else None
    if "recommendation" in changes:
        use_case.recommendation = changes["recommendation"]

    session.add(use_case)
    AuditService(session).append(
        context=context,
        action="use_case.updated",
        entity_type="use_case",
        entity_id=str(use_case.id),
        request_id=str(request.state.request_id),
        before=before,
        after={
            "title": use_case.title,
            "status": use_case.status,
            "owner_membership_id": str(use_case.owner_membership_id)
            if use_case.owner_membership_id
            else None,
        },
        metadata={"changed_fields": sorted(changes)},
    )
    session.commit()
    _refresh_session_scope(session, context)
    session.refresh(use_case)
    return _serialize_use_case(use_case)


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/transition",
    response_model=UseCaseResponse,
)
def transition_use_case_status(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    payload: UseCaseStatusTransitionRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> UseCaseResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_TRANSITION)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    use_case = repository.get_use_case(program, use_case_id)
    if use_case is None:
        raise AppError(status_code=404, title="Not Found", detail="Use case not found.")
    _ensure_transition_authorized(context, payload)
    if payload.target_status not in USE_CASE_TRANSITIONS[use_case.status]:
        raise AppError(
            status_code=409,
            title="Conflict",
            detail=(
                "This endpoint only supports the safe Draft to InProgress handoff. "
                "Submitted and review decisions must use the dedicated assessment and review "
                "actions."
            ),
        )

    before = {
        "status": use_case.status,
        "submitted_at": use_case.submitted_at.isoformat() if use_case.submitted_at else None,
        "approved_at": use_case.approved_at.isoformat() if use_case.approved_at else None,
    }
    use_case.status = payload.target_status
    use_case.submitted_at = None
    use_case.approved_at = None
    session.add(use_case)
    AuditService(session).append(
        context=context,
        action="use_case.transitioned",
        entity_type="use_case",
        entity_id=str(use_case.id),
        request_id=str(request.state.request_id),
        before=before,
        after={
            "status": use_case.status,
            "submitted_at": use_case.submitted_at.isoformat() if use_case.submitted_at else None,
            "approved_at": use_case.approved_at.isoformat() if use_case.approved_at else None,
        },
        metadata={"target_status": use_case.status},
    )
    session.commit()
    _refresh_session_scope(session, context)
    session.refresh(use_case)
    return _serialize_use_case(use_case)
