from __future__ import annotations

import uuid
from typing import Annotated

from app.api.v1.errors import AppError
from app.audit.service import AuditService
from app.db.models.lifecycle import Program, UseCase
from app.db.session import (
    get_session,
    set_postgres_actor,
    set_postgres_workspace,
    set_postgres_workspace_verified,
)
from app.documents.service import DocumentService
from app.schemas.document import DocumentGenerateRequest, DocumentResponse, DocumentVersionResponse
from app.security.auth import AuthContext, get_auth_context
from app.security.roles import Permission
from app.security.tenancy import (
    ScopedRepository,
    ensure_workspace_permission,
    resolve_workspace_context,
)
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session

router = APIRouter(tags=["documents"])
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
) -> tuple[object, Program, UseCase]:
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
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/documents",
    response_model=list[DocumentResponse],
)
def list_documents(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> list[DocumentResponse]:
    context, program, use_case = _resolve_program_and_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    return DocumentService(session, context, request_id="documents.list").list_documents(
        program=program,
        use_case=use_case,
    )


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/documents",
    response_model=DocumentResponse,
)
def generate_document(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    payload: DocumentGenerateRequest,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> DocumentResponse:
    context, program, use_case = _resolve_program_and_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    service = DocumentService(session, context, request_id=str(request.state.request_id))
    result = service.generate_document(
        program=program,
        use_case=use_case,
        document_type=payload.type,
        format_=payload.format,
        language=payload.language,
        idempotency_key=idempotency_key or "",
    )
    current_version = result.current_version
    AuditService(session).append(
        context=context,
        action="document.generated",
        entity_type="document",
        entity_id=str(result.id),
        request_id=str(request.state.request_id),
        after={
            "type": payload.type.value,
            "format": payload.format.value,
            "version_no": current_version.version_no if current_version is not None else None,
            "status": result.status.value,
        },
        metadata={
            "use_case_id": str(use_case.id),
            "program_id": str(program.id),
            "sha256": current_version.sha256 if current_version is not None else None,
        },
    )
    session.commit()
    _refresh_session_scope(session, auth_context, workspace_id)
    return result


@router.get(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/documents/{document_id}/versions",
    response_model=list[DocumentVersionResponse],
)
def list_document_versions(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    document_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> list[DocumentVersionResponse]:
    context, _, use_case = _resolve_program_and_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    return DocumentService(session, context, request_id="documents.versions").list_versions(
        document_id,
        use_case=use_case,
    )


@router.post(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/documents/{document_id}/approve",
    response_model=DocumentResponse,
)
def approve_document(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> DocumentResponse:
    context, program, use_case = _resolve_program_and_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    service = DocumentService(
        session,
        context,
        request_id=str(request.state.request_id),
    )
    result = service.approve_document(
        program=program,
        use_case=use_case,
        document_id=document_id,
    )
    AuditService(session).append(
        context=context,
        action="document.approved",
        entity_type="document",
        entity_id=str(document_id),
        request_id=str(request.state.request_id),
        after={
            "status": result.status.value,
            "current_version_no": result.current_version_no,
        },
        metadata={"program_id": str(program.id)},
    )
    session.commit()
    _refresh_session_scope(session, auth_context, workspace_id)
    return result


@router.get(
    "/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/document-versions/{version_id}/download",
)
def download_document_version(
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    version_id: uuid.UUID,
    request: Request,
    auth_context: AuthContextDependency,
    session: SessionDependency,
):
    context, program, use_case = _resolve_program_and_use_case(
        session=session,
        auth_context=auth_context,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    version, document, content = DocumentService(
        session, context, request_id=str(request.state.request_id)
    ).download_document(program=program, use_case=use_case, version_id=version_id)
    filename = (
        f"{document.type.value}-v{version.version_no}."
        f"{'pdf' if version.format.value == 'pdf' else 'md'}"
    )
    AuditService(session).append(
        context=context,
        action="document.downloaded",
        entity_type="document_version",
        entity_id=str(version.id),
        request_id=str(request.state.request_id),
        after={
            "document_id": str(document.id),
            "version_no": version.version_no,
            "format": version.format.value,
        },
        metadata={"sha256": version.sha256},
    )
    session.commit()
    _refresh_session_scope(session, auth_context, workspace_id)
    return StreamingResponse(
        iter([content]),
        media_type=(
            "application/pdf"
            if version.format.value == "pdf"
            else "text/markdown; charset=utf-8"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Document-SHA256": version.sha256,
            "X-Document-Version-Id": str(version.id),
        },
    )
