from __future__ import annotations

import uuid

import jwt
import pytest
from app.api.v1.errors import AppError
from app.audit.models import AuditEvent
from app.db.models.workspace import MembershipStatus
from app.db.session import get_engine
from app.security.auth import AuthContext, _get_authorization_token, _validate_entra_token
from app.security.dev_auth import (
    contains_dev_headers,
    is_loopback_request,
    require_loopback_request,
)
from app.security.roles import Permission, ProductRole
from app.security.tenancy import (
    ScopedRepository,
    WorkspaceContext,
    decode_cursor,
    encode_cursor,
    ensure_workspace_permission,
    list_actor_workspaces,
    resolve_workspace_context,
)
from fastapi import Request
from sqlmodel import Session

from backend.tests.conftest import (
    configure_entra_env,
    seed_identity,
    seed_membership,
    seed_workspace,
)


def test_dev_auth_helpers_cover_missing_client_and_header_detection() -> None:
    remote_request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-dev-identity", b"dev:actor")],
        }
    )
    loopback_request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "client": ("127.0.0.1", 12345),
            "headers": [(b"x-request-id", b"req-1")],
        }
    )

    assert not is_loopback_request(remote_request)
    assert contains_dev_headers(remote_request)
    assert not contains_dev_headers(loopback_request)
    assert is_loopback_request(loopback_request)
    with pytest.raises(ValueError, match="loopback clients"):
        require_loopback_request(remote_request)


def test_authorization_header_helper_rejects_missing_and_invalid_headers() -> None:
    missing_request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    invalid_request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"authorization", b"Basic nope")],
        }
    )
    valid_request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"authorization", b"Bearer token-value")],
        }
    )

    with pytest.raises(AppError, match="Missing Authorization"):
        _get_authorization_token(missing_request)
    with pytest.raises(AppError, match="Expected"):
        _get_authorization_token(invalid_request)

    assert _get_authorization_token(valid_request) == "token-value"


def test_validate_entra_token_rejects_malformed_or_missing_kid(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
) -> None:
    configure_entra_env(monkeypatch, sqlite_db_url)

    with pytest.raises(AppError, match="Malformed JWT header"):
        _validate_entra_token("not-a-jwt")

    token_without_kid = jwt.encode(
        {
            "iss": "https://login.microsoftonline.com/tenant-123/v2.0",
            "aud": "api://client-123",
            "tid": "tenant-123",
            "oid": "user-123",
            "scp": "access_as_user",
            "roles": ["Consultant"],
        },
        key="secret",
        algorithm="HS256",
        headers={},
    )
    with pytest.raises(AppError, match="JWT kid is required"):
        _validate_entra_token(token_without_kid)


def test_cursor_helpers_and_permission_guard() -> None:
    created_at = seed_workspace_created_at()
    cursor = encode_cursor(created_at, str(uuid.uuid4()))

    decoded = decode_cursor(cursor)

    assert decoded["created_at"] == created_at
    with pytest.raises(AppError, match="Invalid cursor"):
        decode_cursor("invalid-cursor")
    with pytest.raises(AppError, match="Insufficient workspace permissions"):
        ensure_workspace_permission(
            WorkspaceContext(
                workspace=seeded_workspace_placeholder(),
                membership=seeded_membership_placeholder(),
                actor=AuthContext(
                    subject="dev:actor",
                    issuer="dev",
                    tenant_id="dev",
                    oid="actor",
                    display_name="Actor",
                    email="actor@local.dev",
                    token_roles={ProductRole.CONTRIBUTOR},
                ),
                permissions={Permission.WORKSPACE_READ},
            ),
            Permission.MEMBERS_MANAGE,
        )


def test_tenancy_helpers_enforce_scope_and_pagination(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
) -> None:
    from backend.tests.conftest import configure_dev_env, run_upgrade

    configure_dev_env(monkeypatch, sqlite_db_url)
    run_upgrade(sqlite_db_url)

    with Session(get_engine()) as session:
        actor = seed_identity(session, suffix="actor")
        other = seed_identity(session, suffix="other")
        member_one = seed_identity(session, suffix="member-one")
        member_two = seed_identity(session, suffix="member-two")

        workspace = seed_workspace(session, name="Scoped Workspace", created_by=actor)
        actor_secondary_workspace = seed_workspace(
            session,
            name="Actor Secondary Workspace",
            created_by=actor,
        )
        other_workspace = seed_workspace(session, name="Other Workspace", created_by=other)

        actor_membership = seed_membership(
            session,
            workspace=workspace,
            identity=actor,
            role=ProductRole.WORKSPACE_ADMIN,
            created_by=actor,
        )
        seed_membership(
            session,
            workspace=workspace,
            identity=member_one,
            role=ProductRole.CONTRIBUTOR,
            created_by=actor,
        )
        seed_membership(
            session,
            workspace=workspace,
            identity=member_two,
            role=ProductRole.SPONSOR,
            created_by=actor,
        )
        seed_membership(
            session,
            workspace=actor_secondary_workspace,
            identity=actor,
            role=ProductRole.CONTRIBUTOR,
            created_by=actor,
        )
        seed_membership(
            session,
            workspace=other_workspace,
            identity=other,
            role=ProductRole.WORKSPACE_ADMIN,
            created_by=other,
        )
        audit_event = AuditEvent(
            workspace_id=workspace.id,
            actor_subject_id=actor.id,
            action="workspace.created",
            entity_type="workspace",
            entity_id=str(workspace.id),
            request_id="request-1",
        )
        session.add(audit_event)
        session.commit()

        actor_context = AuthContext(
            subject="dev:actor",
            issuer="dev",
            tenant_id="dev",
            oid="actor",
            display_name="Actor",
            email="actor@local.dev",
            token_roles={ProductRole.WORKSPACE_ADMIN},
            identity_subject_id=actor.id,
        )
        context = resolve_workspace_context(session, actor_context, workspace.id)
        repository = ScopedRepository(session, context)

        rows, next_cursor = repository.list_memberships(limit=1, cursor=None)
        paged_rows, _ = repository.list_memberships(limit=5, cursor=next_cursor)
        actor_workspaces, workspace_cursor = list_actor_workspaces(
            session,
            actor_context,
            cursor=None,
            limit=1,
        )
        subsequent_workspaces, _ = list_actor_workspaces(
            session,
            actor_context,
            cursor=workspace_cursor,
            limit=5,
        )

        assert context.workspace.id == workspace.id
        assert context.membership.id == actor_membership.id
        assert context.permissions == {
            Permission.WORKSPACE_READ,
            Permission.WORKSPACE_UPDATE,
            Permission.MEMBERS_READ,
            Permission.MEMBERS_MANAGE,
            Permission.PROGRAM_CREATE,
            Permission.PROGRAM_READ,
            Permission.PROGRAM_UPDATE,
            Permission.PROGRAM_ASSIGN,
            Permission.USE_CASE_CREATE,
            Permission.USE_CASE_READ,
            Permission.USE_CASE_UPDATE,
            Permission.USE_CASE_TRANSITION,
        }
        assert len(rows) == 1
        assert next_cursor is not None
        assert len(paged_rows) == 2
        assert repository.get_membership(rows[0][0].id) is not None
        assert repository.list_audit_events()[0].id == audit_event.id
        assert len(actor_workspaces) == 1
        assert workspace_cursor is not None
        assert len(subsequent_workspaces) == 1

        mismatched_context = WorkspaceContext(
            workspace=context.workspace,
            membership=context.membership,
            actor=context.actor,
            permissions=context.permissions,
        )
        with pytest.raises(AppError, match="Workspace mismatch"):
            repository.create_membership(
                seeded_membership_placeholder(
                    membership_workspace_id=other_workspace.id,
                    identity_subject_id=actor.id,
                )
            )
        with pytest.raises(AppError, match="Workspace not found"):
            resolve_workspace_context(
                session,
                AuthContext(
                    subject="dev:none",
                    issuer="dev",
                    tenant_id="dev",
                    oid="none",
                    display_name=None,
                    email=None,
                    token_roles={ProductRole.CONTRIBUTOR},
                ),
                workspace.id,
            )
        with pytest.raises(AppError, match="Workspace not found"):
            resolve_workspace_context(
                session,
                AuthContext(
                    subject="dev:other",
                    issuer="dev",
                    tenant_id="dev",
                    oid="other",
                    display_name="Other",
                    email="other@local.dev",
                    token_roles={ProductRole.WORKSPACE_ADMIN},
                    identity_subject_id=other.id,
                ),
                workspace.id,
            )
        assert list_actor_workspaces(
            session,
            AuthContext(
                subject="dev:unknown",
                issuer="dev",
                tenant_id="dev",
                oid="unknown",
                display_name=None,
                email=None,
                token_roles={ProductRole.CONTRIBUTOR},
            ),
            cursor=None,
            limit=5,
        ) == ([], None)
        assert mismatched_context.workspace.id == workspace.id


def test_workspace_admin_membership_does_not_override_consultant_token(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
) -> None:
    from backend.tests.conftest import configure_dev_env, run_upgrade

    configure_dev_env(monkeypatch, sqlite_db_url)
    run_upgrade(sqlite_db_url)

    with Session(get_engine()) as session:
        actor = seed_identity(session, suffix="actor")
        workspace = seed_workspace(session, name="Scoped Workspace", created_by=actor)
        seed_membership(
            session,
            workspace=workspace,
            identity=actor,
            role=ProductRole.WORKSPACE_ADMIN,
            created_by=actor,
        )
        session.commit()

        consultant_context = resolve_workspace_context(
            session,
            AuthContext(
                subject="dev:actor",
                issuer="dev",
                tenant_id="dev",
                oid="actor",
                display_name="Actor",
                email="actor@local.dev",
                token_roles={ProductRole.CONSULTANT},
                identity_subject_id=actor.id,
            ),
            workspace.id,
        )

        assert consultant_context.permissions == {
            Permission.WORKSPACE_READ,
            Permission.PROGRAM_CREATE,
            Permission.PROGRAM_READ,
            Permission.PROGRAM_UPDATE,
            Permission.PROGRAM_ASSIGN,
            Permission.USE_CASE_CREATE,
            Permission.USE_CASE_READ,
            Permission.USE_CASE_UPDATE,
            Permission.USE_CASE_TRANSITION,
        }


def seed_workspace_created_at():
    from datetime import UTC, datetime

    return datetime.now(UTC).replace(microsecond=0)


def seeded_workspace_placeholder():
    from app.db.models.workspace import Workspace

    return Workspace(
        name="Workspace",
        default_language="en",
        confidentiality_policy="internal-only",
        created_by_subject_id=uuid.uuid4(),
    )


def seeded_membership_placeholder(
    *,
    membership_workspace_id: uuid.UUID | None = None,
    identity_subject_id: uuid.UUID | None = None,
):
    from app.db.models.workspace import WorkspaceMembership

    return WorkspaceMembership(
        workspace_id=membership_workspace_id or uuid.uuid4(),
        identity_subject_id=identity_subject_id or uuid.uuid4(),
        role=ProductRole.CONTRIBUTOR.value,
        status=MembershipStatus.ACTIVE,
        created_by_subject_id=uuid.uuid4(),
    )
