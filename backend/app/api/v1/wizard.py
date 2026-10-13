from __future__ import annotations

import uuid
from typing import Annotated

from app.api.v1.errors import AppError
from app.db.models.lifecycle import UseCase
from app.db.session import (
    get_session,
    set_postgres_actor,
    set_postgres_workspace,
    set_postgres_workspace_verified,
)
from app.llm.schemas import KickstartSuggestionResponse
from app.llm.service import LlmAssistanceService
from app.schemas.wizard import (
    AnswerResponse,
    AnswerUpsertRequest,
    AssessmentCreateRequest,
    AssessmentEnvelopeResponse,
    AssessmentSubmitResponse,
    StepValidationResponse,
)
from app.security.auth import AuthContext, get_auth_context
from app.security.roles import Permission
from app.security.tenancy import (
    ScopedRepository,
    ensure_workspace_permission,
    resolve_workspace_context,
)
from app.wizard.service import WizardService
from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

router = APIRouter(tags=["wizard"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[Session, Depends(get_session)]


def _refresh_session_scope(
    session: Session, auth_context: AuthContext, workspace_id: uuid.UUID
) -> None:
    if auth_context.identity_subject_id is not None:
        set_postgres_actor(session, str(auth_context.identity_subject_id))
    set_postgres_workspace(session, str(workspace_id))
    set_postgres_workspace_verified(session)


def _resolve_program_and_use_case(
    *,
    session: Session,
    auth_context: AuthContext,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
) -> tuple[ScopedRepository, UseCase]:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_READ)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    use_case = repository.get_use_case(program, use_case_id)
    if use_case is None:
        raise AppError(status_code=404, title="Not Found", detail="Use case not found.")
    return repository, use_case


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/assessments",
    response_model=AssessmentEnvelopeResponse,
    status_code=201,
)
def create_assessment(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    payload: AssessmentCreateRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> AssessmentEnvelopeResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_READ)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    use_case = repository.get_use_case(program, use_case_id)
    if use_case is None:
        raise AppError(status_code=404, title="Not Found", detail="Use case not found.")

    envelope = WizardService(
        session,
        context,
        str(request.state.request_id),
    ).create_or_reopen_draft(program=program, use_case=use_case, payload=payload)
    session.commit()
    _refresh_session_scope(session, auth_context, workspace_id)
    return envelope


@router.get(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/assessments/current",
    response_model=AssessmentEnvelopeResponse,
)
def get_current_assessment(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> AssessmentEnvelopeResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_READ)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    use_case = repository.get_use_case(program, use_case_id)
    if use_case is None:
        raise AppError(status_code=404, title="Not Found", detail="Use case not found.")
    return WizardService(session, context, "assessment-current").get_current_assessment(use_case)


@router.get(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/assessments/{assessment_id}",
    response_model=AssessmentEnvelopeResponse,
)
def get_assessment(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    assessment_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> AssessmentEnvelopeResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_READ)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    use_case = repository.get_use_case(program, use_case_id)
    if use_case is None:
        raise AppError(status_code=404, title="Not Found", detail="Use case not found.")
    return WizardService(session, context, "assessment-get").get_assessment(
        assessment_id=assessment_id,
        expected_use_case_id=use_case.id,
    )


@router.put(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/assessments/{assessment_id}/answers/{question_key}",
    response_model=AnswerResponse,
)
def upsert_assessment_answer(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    assessment_id: uuid.UUID,
    question_key: str,
    payload: AnswerUpsertRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> AnswerResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_READ)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    use_case = repository.get_use_case(program, use_case_id)
    if use_case is None:
        raise AppError(status_code=404, title="Not Found", detail="Use case not found.")
    response = WizardService(session, context, str(request.state.request_id)).upsert_answer(
        assessment_id=assessment_id,
        expected_use_case_id=use_case.id,
        question_key=question_key,
        payload=payload,
    )
    session.commit()
    _refresh_session_scope(session, auth_context, workspace_id)
    return response


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/assessments/{assessment_id}/kickstart",
    response_model=KickstartSuggestionResponse,
)
def generate_assessment_kickstart(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    assessment_id: uuid.UUID,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> KickstartSuggestionResponse:
    repository, use_case = _resolve_program_and_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")

    response = LlmAssistanceService(
        session, repository.context, str(request.state.request_id)
    )
    try:
        result = response.generate_kickstart(
            assessment_id=str(assessment_id),
            expected_use_case_id=use_case.id,
            program=program,
            use_case=use_case,
        )
    except AppError:
        session.commit()
        raise
    session.commit()
    _refresh_session_scope(session, auth_context, workspace_id)
    return result


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/assessments/{assessment_id}/validate-step/{step}",
    response_model=StepValidationResponse,
)
def validate_assessment_step(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    assessment_id: uuid.UUID,
    step: int,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> StepValidationResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_READ)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    use_case = repository.get_use_case(program, use_case_id)
    if use_case is None:
        raise AppError(status_code=404, title="Not Found", detail="Use case not found.")
    return WizardService(session, context, "assessment-validate").validate_step(
        assessment_id=assessment_id,
        expected_use_case_id=use_case.id,
        step=step,
    )


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/assessments/{assessment_id}/submit",
    response_model=AssessmentSubmitResponse,
)
def submit_assessment(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    assessment_id: uuid.UUID,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> AssessmentSubmitResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_READ)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    use_case = repository.get_use_case(program, use_case_id)
    if use_case is None:
        raise AppError(status_code=404, title="Not Found", detail="Use case not found.")
    response = WizardService(session, context, str(request.state.request_id)).submit(
        assessment_id=assessment_id,
        use_case=use_case,
    )
    session.commit()
    _refresh_session_scope(session, auth_context, workspace_id)
    return response
