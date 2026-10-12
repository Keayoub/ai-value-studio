from __future__ import annotations

import uuid
from typing import Annotated

from app.api.v1.errors import AppError
from app.audit.service import AuditService
from app.db.models.lifecycle import Program, ProgramMember, ProgramStatus
from app.db.models.workspace import WorkspaceMembership
from app.db.session import (
    get_session,
    set_postgres_actor,
    set_postgres_workspace,
    set_postgres_workspace_verified,
)
from app.schemas.common import CursorPageResponse
from app.schemas.lifecycle import (
    ProgramCreateRequest,
    ProgramMemberCreateRequest,
    ProgramMemberResponse,
    ProgramResponse,
    ProgramStatusTransitionRequest,
    ProgramUpdateRequest,
)
from app.security.auth import AuthContext, get_auth_context
from app.security.roles import Permission
from app.security.tenancy import (
    ScopedRepository,
    ensure_workspace_permission,
    resolve_workspace_context,
)
from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

router = APIRouter(tags=["programs"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[Session, Depends(get_session)]

PROGRAM_TRANSITIONS: dict[ProgramStatus, set[ProgramStatus]] = {
    ProgramStatus.DRAFT: {ProgramStatus.DISCOVERY, ProgramStatus.CLOSED},
    ProgramStatus.DISCOVERY: {ProgramStatus.ASSESSMENT, ProgramStatus.CLOSED},
    ProgramStatus.ASSESSMENT: {ProgramStatus.PRIORITIZATION, ProgramStatus.CLOSED},
    ProgramStatus.PRIORITIZATION: {ProgramStatus.DECISION, ProgramStatus.CLOSED},
    ProgramStatus.DECISION: {ProgramStatus.CLOSED},
    ProgramStatus.CLOSED: set(),
}


def _serialize_program(program: Program) -> ProgramResponse:
    return ProgramResponse(
        id=program.id,
        workspace_id=program.workspace_id,
        name=program.name,
        strategic_objective=program.strategic_objective,
        departments=list(program.departments_json or []),
        period_start=program.period_start,
        period_end=program.period_end,
        sponsor_membership_id=program.sponsor_membership_id,
        consultant_membership_id=program.consultant_membership_id,
        target_use_case_count=program.target_use_case_count,
        questionnaire_template_version_id=program.questionnaire_template_version_id,
        confidentiality_level=program.confidentiality_level,
        status=program.status,
        created_by_subject_id=program.created_by_subject_id,
        created_at=program.created_at,
        updated_at=program.updated_at,
    )


def _serialize_program_member(program_member: ProgramMember) -> ProgramMemberResponse:
    return ProgramMemberResponse(
        id=program_member.id,
        workspace_id=program_member.workspace_id,
        program_id=program_member.program_id,
        membership_id=program_member.membership_id,
        assignment_role=program_member.assignment_role,
        created_by_subject_id=program_member.created_by_subject_id,
        created_at=program_member.created_at,
        updated_at=program_member.updated_at,
    )


def _resolve_workspace_member(
    repository: ScopedRepository,
    membership_id: uuid.UUID | None,
    *,
    detail: str,
) -> WorkspaceMembership | None:
    if membership_id is None:
        return None
    membership = repository.resolve_workspace_membership(membership_id)
    if membership is None:
        raise AppError(status_code=404, title="Not Found", detail=detail)
    return membership


@router.get(
    "/workspaces/{workspace_id}/programs",
    response_model=CursorPageResponse[ProgramResponse],
)
def list_programs(
    workspace_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> CursorPageResponse[ProgramResponse]:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.PROGRAM_READ)
    rows, next_cursor = ScopedRepository(session, context).list_programs(limit=limit, cursor=cursor)
    return CursorPageResponse(
        items=[_serialize_program(program) for program in rows],
        next_cursor=next_cursor,
    )


@router.post("/workspaces/{workspace_id}/programs", response_model=ProgramResponse, status_code=201)
def create_program(
    workspace_id: uuid.UUID,
    payload: ProgramCreateRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> ProgramResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.PROGRAM_CREATE)
    repository = ScopedRepository(session, context)
    sponsor_membership = _resolve_workspace_member(
        repository,
        payload.sponsor_membership_id,
        detail="Sponsor membership not found in this workspace.",
    )
    consultant_membership = _resolve_workspace_member(
        repository,
        payload.consultant_membership_id,
        detail="Consultant membership not found in this workspace.",
    )

    program = Program(
        workspace_id=context.workspace.id,
        name=payload.name,
        strategic_objective=payload.strategic_objective,
        departments_json=payload.departments,
        period_start=payload.period_start,
        period_end=payload.period_end,
        sponsor_membership_id=sponsor_membership.id if sponsor_membership is not None else None,
        consultant_membership_id=(
            consultant_membership.id if consultant_membership is not None else None
        ),
        target_use_case_count=payload.target_use_case_count,
        questionnaire_template_version_id=payload.questionnaire_template_version_id,
        confidentiality_level=payload.confidentiality_level,
        created_by_subject_id=context.membership.identity_subject_id,
    )
    repository.create_program(program)
    session.flush()

    AuditService(session).append(
        context=context,
        action="program.created",
        entity_type="program",
        entity_id=str(program.id),
        request_id=str(request.state.request_id),
        after={"name": program.name, "status": program.status},
        metadata={
            "sponsor_membership_id": str(program.sponsor_membership_id)
            if program.sponsor_membership_id
            else None,
            "consultant_membership_id": str(program.consultant_membership_id)
            if program.consultant_membership_id
            else None,
        },
    )
    _refresh_session_scope(session, context)
    session.commit()
    _refresh_session_scope(session, context)
    session.refresh(program)
    return _serialize_program(program)


@router.get("/workspaces/{workspace_id}/programs/{program_id}", response_model=ProgramResponse)
def get_program(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> ProgramResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.PROGRAM_READ)
    program = ScopedRepository(session, context).get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    return _serialize_program(program)


@router.patch("/workspaces/{workspace_id}/programs/{program_id}", response_model=ProgramResponse)
def update_program(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    payload: ProgramUpdateRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> ProgramResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.PROGRAM_UPDATE)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")

    before = {
        "name": program.name,
        "status": program.status,
        "sponsor_membership_id": str(program.sponsor_membership_id)
        if program.sponsor_membership_id
        else None,
        "consultant_membership_id": str(program.consultant_membership_id)
        if program.consultant_membership_id
        else None,
    }
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        program.name = changes["name"]
    if "strategic_objective" in changes:
        program.strategic_objective = changes["strategic_objective"]
    if "departments" in changes:
        program.departments_json = changes["departments"]
    if "period_start" in changes:
        program.period_start = changes["period_start"]
    if "period_end" in changes:
        program.period_end = changes["period_end"]
    if "sponsor_membership_id" in changes:
        sponsor_membership = _resolve_workspace_member(
            repository,
            changes["sponsor_membership_id"],
            detail="Sponsor membership not found in this workspace.",
        )
        program.sponsor_membership_id = sponsor_membership.id if sponsor_membership else None
    if "consultant_membership_id" in changes:
        consultant_membership = _resolve_workspace_member(
            repository,
            changes["consultant_membership_id"],
            detail="Consultant membership not found in this workspace.",
        )
        program.consultant_membership_id = (
            consultant_membership.id if consultant_membership else None
        )
    if "target_use_case_count" in changes:
        program.target_use_case_count = changes["target_use_case_count"]
    if "questionnaire_template_version_id" in changes:
        program.questionnaire_template_version_id = changes["questionnaire_template_version_id"]
    if "confidentiality_level" in changes:
        program.confidentiality_level = changes["confidentiality_level"]

    session.add(program)
    AuditService(session).append(
        context=context,
        action="program.updated",
        entity_type="program",
        entity_id=str(program.id),
        request_id=str(request.state.request_id),
        before=before,
        after={
            "name": program.name,
            "status": program.status,
            "sponsor_membership_id": str(program.sponsor_membership_id)
            if program.sponsor_membership_id
            else None,
            "consultant_membership_id": str(program.consultant_membership_id)
            if program.consultant_membership_id
            else None,
        },
        metadata={"changed_fields": sorted(changes)},
    )
    session.commit()
    _refresh_session_scope(session, context)
    session.refresh(program)
    return _serialize_program(program)


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/transition",
    response_model=ProgramResponse,
)
def transition_program_status(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    payload: ProgramStatusTransitionRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> ProgramResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.PROGRAM_UPDATE)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    if payload.target_status not in PROGRAM_TRANSITIONS[program.status]:
        raise AppError(
            status_code=409,
            title="Conflict",
            detail=f"Cannot transition program from {program.status} to {payload.target_status}.",
        )

    before = {"status": program.status}
    program.status = payload.target_status
    session.add(program)
    AuditService(session).append(
        context=context,
        action="program.transitioned",
        entity_type="program",
        entity_id=str(program.id),
        request_id=str(request.state.request_id),
        before=before,
        after={"status": program.status},
        metadata={"target_status": program.status},
    )
    session.commit()
    _refresh_session_scope(session, context)
    session.refresh(program)
    return _serialize_program(program)


@router.get(
    "/workspaces/{workspace_id}/programs/{program_id}/members",
    response_model=CursorPageResponse[ProgramMemberResponse],
)
def list_program_members(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> CursorPageResponse[ProgramMemberResponse]:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.PROGRAM_ASSIGN)
    repository = ScopedRepository(session, context)
    if repository.get_program(program_id) is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    rows, next_cursor = repository.list_program_members(program_id, limit=limit, cursor=cursor)
    return CursorPageResponse(
        items=[_serialize_program_member(program_member) for program_member in rows],
        next_cursor=next_cursor,
    )


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/members",
    response_model=ProgramMemberResponse,
    status_code=201,
)
def create_program_member(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    payload: ProgramMemberCreateRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> ProgramMemberResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.PROGRAM_ASSIGN)
    repository = ScopedRepository(session, context)
    if repository.get_program(program_id) is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    membership = _resolve_workspace_member(
        repository,
        payload.membership_id,
        detail="Workspace membership not found.",
    )
    if membership is None:
        raise AppError(status_code=404, title="Not Found", detail="Workspace membership not found.")
    existing = repository.get_program_member(program_id, membership.id)
    if existing is not None:
        raise AppError(
            status_code=409,
            title="Conflict",
            detail="Program assignment already exists for this membership.",
        )

    program_member = ProgramMember(
        workspace_id=context.workspace.id,
        program_id=program_id,
        membership_id=membership.id,
        assignment_role=payload.assignment_role,
        created_by_subject_id=context.membership.identity_subject_id,
    )
    repository.create_program_member(program_member)
    session.flush()

    AuditService(session).append(
        context=context,
        action="program_member.created",
        entity_type="program_member",
        entity_id=str(program_member.id),
        request_id=str(request.state.request_id),
        after={
            "membership_id": str(program_member.membership_id),
            "assignment_role": program_member.assignment_role,
        },
    )
    session.commit()
    _refresh_session_scope(session, context)
    session.refresh(program_member)
    return _serialize_program_member(program_member)


def _refresh_session_scope(session: Session, context) -> None:
    if context.actor.identity_subject_id is not None:
        set_postgres_actor(session, str(context.actor.identity_subject_id))
    set_postgres_workspace(session, str(context.workspace.id))
    set_postgres_workspace_verified(session)
