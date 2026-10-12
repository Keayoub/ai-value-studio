from __future__ import annotations

import uuid
from typing import Annotated

from app.api.v1.errors import AppError
from app.audit.service import AuditService
from app.db.models.lifecycle import ApprovalDecision, UseCase
from app.db.session import (
    get_session,
    set_postgres_actor,
    set_postgres_workspace,
    set_postgres_workspace_verified,
)
from app.reviews.service import ReviewService
from app.schemas.common import CursorPageResponse
from app.schemas.review import (
    ReviewCommentCreateRequest,
    ReviewCommentResponse,
    ReviewCreateRequest,
    ReviewDecisionRequest,
    ReviewInboxItemResponse,
    ReviewStateResponse,
)
from app.security.auth import AuthContext, get_auth_context
from app.security.roles import Permission
from app.security.tenancy import (
    ScopedRepository,
    ensure_workspace_permission,
    resolve_workspace_context,
)
from fastapi import APIRouter, Depends, Header, Query, Request
from sqlmodel import Session

router = APIRouter(tags=["reviews"])
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
) -> tuple[object, object, UseCase]:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_READ)
    repository = ScopedRepository(session, context)
    program = repository.get_program(program_id)
    if program is None:
        raise AppError(status_code=404, title="Not Found", detail="Program not found.")
    use_case = repository.get_use_case(program, use_case_id)
    if use_case is None:
        raise AppError(status_code=404, title="Not Found", detail="Use case not found.")
    return context, program, use_case


@router.get(
    "/workspaces/{workspace_id}/review-inbox",
    response_model=CursorPageResponse[ReviewInboxItemResponse],
)
def list_review_inbox(
    workspace_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> CursorPageResponse[ReviewInboxItemResponse]:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_READ)
    return ReviewService(session, context).list_inbox(limit=limit, cursor=cursor)


@router.get(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/review",
    response_model=ReviewStateResponse,
)
def get_review_state(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> ReviewStateResponse:
    context, program, use_case = _resolve_program_and_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    return ReviewService(session, context).get_review_state(program=program, use_case=use_case)


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews",
    response_model=ReviewStateResponse,
)
def create_review(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    payload: ReviewCreateRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> ReviewStateResponse:
    context, program, use_case = _resolve_program_and_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    state = ReviewService(session, context).create_review(
        program=program,
        use_case=use_case,
        payload=payload,
    )
    review = state.review
    if review is None:
        raise AppError(
            status_code=500,
            title="Internal Server Error",
            detail="Review creation did not produce a review state.",
        )
    AuditService(session).append(
        context=context,
        action="review.created",
        entity_type="review",
        entity_id=str(review.id),
        request_id=str(request.state.request_id),
        before=None,
        after={
            "status": review.status,
            "recommendation": review.recommendation,
            "assessment_version": review.assessment_version,
        },
        metadata={"use_case_id": str(use_case.id)},
    )
    session.commit()
    _refresh_session_scope(session, auth_context, workspace_id)
    return state


@router.get(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/comments",
    response_model=list[ReviewCommentResponse],
)
def list_review_comments(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> list[ReviewCommentResponse]:
    context, program, use_case = _resolve_program_and_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    return ReviewService(session, context).get_review_state(
        program=program,
        use_case=use_case,
    ).comments


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/comments",
    response_model=ReviewCommentResponse,
)
def create_review_comment(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    payload: ReviewCommentCreateRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> ReviewCommentResponse:
    context, program, use_case = _resolve_program_and_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    comment = ReviewService(session, context).add_comment(
        program=program,
        use_case=use_case,
        payload=payload,
    )
    AuditService(session).append(
        context=context,
        action="review.commented",
        entity_type="review_comment",
        entity_id=str(comment.id),
        request_id=str(request.state.request_id),
        after={
            "review_id": str(comment.review_id),
            "parent_comment_id": (
                str(comment.parent_comment_id) if comment.parent_comment_id else None
            ),
        },
        metadata={"use_case_id": str(use_case.id)},
    )
    session.commit()
    _refresh_session_scope(session, auth_context, workspace_id)
    return comment


def _resolve_idempotency_key(idempotency_key: str | None) -> str:
    key = (idempotency_key or "").strip()
    if not key:
        raise AppError(
            status_code=400,
            title="Bad Request",
            detail="Idempotency-Key header is required for review decisions.",
        )
    return key


def _decide_review(
    *,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    review_id: uuid.UUID,
    decision: ApprovalDecision,
    payload: ReviewDecisionRequest,
    request: Request,
    idempotency_key: str | None,
    auth_context: AuthContext,
    session: Session,
) -> ReviewStateResponse:
    context, program, use_case = _resolve_program_and_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    result = ReviewService(session, context).decide_review(
        program=program,
        use_case=use_case,
        review_id=review_id,
        decision=decision,
        decision_reason=(payload.decision_reason or "").strip(),
        idempotency_key=_resolve_idempotency_key(idempotency_key),
    )
    if result.audit_action is not None:
        AuditService(session).append(
            context=context,
            action=result.audit_action,
            entity_type="approval",
            entity_id=str(result.approval.id),
            request_id=str(request.state.request_id),
            after={
                "review_id": str(review_id),
                "decision": decision.value,
                "use_case_status": use_case.status,
            },
            metadata={
                "use_case_id": str(use_case.id),
                **(result.audit_metadata or {}),
            },
        )
        session.commit()
        _refresh_session_scope(session, auth_context, workspace_id)
    elif not result.replayed:
        AuditService(session).append(
            context=context,
            action=f"review.{decision.value.lower()}",
            entity_type="approval",
            entity_id=str(result.approval.id),
            request_id=str(request.state.request_id),
            before=result.review_before,
            after=result.review_after,
            metadata={"use_case_id": str(use_case.id)},
        )
        if result.use_case_before is not None and result.use_case_after is not None:
            AuditService(session).append(
                context=context,
                action="use_case.transitioned",
                entity_type="use_case",
                entity_id=str(use_case.id),
                request_id=str(request.state.request_id),
                before=result.use_case_before,
                after=result.use_case_after,
                metadata={
                    "source": f"review.{decision.value.lower()}",
                    "target_status": use_case.status,
                    "review_id": str(review_id),
                },
            )
        session.commit()
        _refresh_session_scope(session, auth_context, workspace_id)
    return result.state


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/approve",
    response_model=ReviewStateResponse,
)
def approve_review(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    review_id: uuid.UUID,
    payload: ReviewDecisionRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReviewStateResponse:
    return _decide_review(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        review_id=review_id,
        decision=ApprovalDecision.APPROVED,
        payload=payload,
        request=request,
        idempotency_key=idempotency_key,
        auth_context=auth_context,
        session=session,
    )


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/reject",
    response_model=ReviewStateResponse,
)
def reject_review(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    review_id: uuid.UUID,
    payload: ReviewDecisionRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReviewStateResponse:
    return _decide_review(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        review_id=review_id,
        decision=ApprovalDecision.REJECTED,
        payload=payload,
        request=request,
        idempotency_key=idempotency_key,
        auth_context=auth_context,
        session=session,
    )


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/request-changes",
    response_model=ReviewStateResponse,
)
def request_review_changes(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    review_id: uuid.UUID,
    payload: ReviewDecisionRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReviewStateResponse:
    return _decide_review(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        review_id=review_id,
        decision=ApprovalDecision.CHANGES_REQUESTED,
        payload=payload,
        request=request,
        idempotency_key=idempotency_key,
        auth_context=auth_context,
        session=session,
    )
