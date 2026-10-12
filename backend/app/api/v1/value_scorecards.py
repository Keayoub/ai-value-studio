from __future__ import annotations

import uuid
from typing import Annotated

from app.api.v1.errors import AppError
from app.audit.service import AuditService
from app.db.models.lifecycle import UseCase
from app.db.session import (
    get_session,
    set_postgres_actor,
    set_postgres_workspace,
    set_postgres_workspace_verified,
)
from app.schemas.value_score import (
    ScorecardOverrideRequest,
    UseCaseScorecardResponse,
    ValueAssessmentUpsertRequest,
)
from app.security.auth import AuthContext, get_auth_context
from app.security.roles import Permission
from app.security.tenancy import (
    ScopedRepository,
    ensure_workspace_permission,
    resolve_workspace_context,
)
from app.value_scoring.service import ValueScoringService
from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

router = APIRouter(tags=["value-scorecards"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[Session, Depends(get_session)]


def _refresh_session_scope(
    session: Session, auth_context: AuthContext, workspace_id: uuid.UUID
) -> None:
    if auth_context.identity_subject_id is not None:
        set_postgres_actor(session, str(auth_context.identity_subject_id))
    set_postgres_workspace(session, str(workspace_id))
    set_postgres_workspace_verified(session)


def _resolve_use_case(
    *,
    session: Session,
    auth_context: AuthContext,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
) -> tuple[object, UseCase]:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_READ)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    use_case = repository.get_use_case(program, use_case_id)
    if use_case is None:
        raise AppError(status_code=404, title="Not Found", detail="Use case not found.")
    return context, use_case


@router.get(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/scorecards",
    response_model=UseCaseScorecardResponse,
)
def get_scorecards(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> UseCaseScorecardResponse:
    context, use_case = _resolve_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    service = ValueScoringService(session, context)
    response = service.get_scorecards(use_case)
    if service.mutated:
        session.commit()
        _refresh_session_scope(session, auth_context, workspace_id)
    return response


@router.put(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/value-assessment",
    response_model=UseCaseScorecardResponse,
)
def put_value_assessment(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    payload: ValueAssessmentUpsertRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> UseCaseScorecardResponse:
    context, use_case = _resolve_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    service = ValueScoringService(session, context)
    before = service.get_scorecards(use_case).value_assessment.input_snapshot
    response = service.upsert_value_assessment(use_case, payload)
    AuditService(session).append(
        context=context,
        action="value_assessment.updated",
        entity_type="value_assessment",
        entity_id=str(response.value_assessment.id),
        request_id=str(request.state.request_id),
        before=before,
        after=response.value_assessment.input_snapshot,
        metadata={"use_case_id": str(use_case.id)},
    )
    session.commit()
    _refresh_session_scope(session, auth_context, workspace_id)
    return response


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/scorecards/recalculate",
    response_model=UseCaseScorecardResponse,
)
def recalculate_scorecards(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> UseCaseScorecardResponse:
    context, use_case = _resolve_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    service = ValueScoringService(session, context)
    response = service.recalculate_scorecard(use_case)
    current = response.current_scorecard
    if current is None:
        raise AppError(
            status_code=500,
            title="Internal Server Error",
            detail="Scorecard recalculation did not produce a current version.",
        )
    AuditService(session).append(
        context=context,
        action="scorecard.recalculated",
        entity_type="scorecard_version",
        entity_id=str(current.id),
        request_id=str(request.state.request_id),
        after={
            "version": current.version,
            "priority_score": current.priority_score,
            "category": current.category,
        },
        metadata={"use_case_id": str(use_case.id)},
    )
    session.commit()
    _refresh_session_scope(session, auth_context, workspace_id)
    return response


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/scorecards/override",
    response_model=UseCaseScorecardResponse,
)
def override_scorecard(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    payload: ScorecardOverrideRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> UseCaseScorecardResponse:
    context, use_case = _resolve_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    service = ValueScoringService(session, context)
    response = service.override_scorecard(use_case, payload)
    current = response.current_scorecard
    if current is None:
        raise AppError(
            status_code=500,
            title="Internal Server Error",
            detail="Scorecard override did not produce a current version.",
        )
    AuditService(session).append(
        context=context,
        action="scorecard.overridden",
        entity_type="scorecard_version",
        entity_id=str(current.id),
        request_id=str(request.state.request_id),
        after={
            "version": current.version,
            "dimension": payload.dimension.value,
            "score": payload.score,
        },
        metadata={"use_case_id": str(use_case.id), "reason": payload.reason},
    )
    session.commit()
    _refresh_session_scope(session, auth_context, workspace_id)
    return response
