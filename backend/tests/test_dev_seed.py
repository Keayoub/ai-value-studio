from __future__ import annotations

import pytest
from app.audit.models import AuditEvent
from app.config import clear_settings_cache
from app.db.models.identity import IdentitySubject
from app.db.models.workspace import Workspace, WorkspaceMembership
from app.db.session import clear_engine_cache, get_engine
from sqlmodel import Session, select

from backend.scripts import dev_seed
from backend.tests.conftest import configure_dev_env, configure_entra_env, run_upgrade


def _refresh_runtime_state() -> None:
    clear_settings_cache()
    clear_engine_cache()


def _snapshot_seed_state(session: Session) -> dict[str, object]:
    workspaces = list(session.exec(select(Workspace).order_by(Workspace.id)).all())
    identities = list(session.exec(select(IdentitySubject).order_by(IdentitySubject.subject)).all())
    memberships = list(
        session.exec(
            select(WorkspaceMembership).order_by(
                WorkspaceMembership.workspace_id,
                WorkspaceMembership.identity_subject_id,
            )
        ).all()
    )
    audit_events = list(session.exec(select(AuditEvent).order_by(AuditEvent.id)).all())
    return {
        "workspace_count": len(workspaces),
        "identity_count": len(identities),
        "membership_count": len(memberships),
        "audit_event_count": len(audit_events),
        "workspaces": [
            (
                workspace.id,
                workspace.name,
                workspace.description,
                workspace.created_by_subject_id,
                workspace.created_at,
                workspace.updated_at,
            )
            for workspace in workspaces
        ],
        "identities": [
            (
                identity.id,
                identity.subject,
                identity.issuer,
                identity.tenant_id,
                identity.oid,
                identity.display_name,
                identity.email,
                identity.created_at,
                identity.updated_at,
            )
            for identity in identities
        ],
        "memberships": [
            (
                membership.id,
                membership.workspace_id,
                membership.identity_subject_id,
                membership.role,
                membership.status,
                membership.created_by_subject_id,
                membership.created_at,
                membership.updated_at,
            )
            for membership in memberships
        ],
        "audit_events": [
            (
                event.id,
                event.workspace_id,
                event.actor_subject_id,
                event.action,
                event.entity_type,
                event.entity_id,
                event.request_id,
                event.occurred_at,
                event.before_hash,
                event.after_hash,
                event.metadata_json,
                event.ip_hash,
            )
            for event in audit_events
        ],
    }


def test_dev_seed_is_idempotent_on_migrated_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
) -> None:
    configure_dev_env(monkeypatch, sqlite_db_url)
    run_upgrade(sqlite_db_url)
    _refresh_runtime_state()

    dev_seed.main()
    with Session(get_engine()) as session:
        first_snapshot = _snapshot_seed_state(session)

    dev_seed.main()
    with Session(get_engine()) as session:
        second_snapshot = _snapshot_seed_state(session)

    assert first_snapshot["workspace_count"] == 1
    assert first_snapshot["identity_count"] == 4
    assert first_snapshot["membership_count"] == 4
    assert first_snapshot["audit_event_count"] == 1
    assert first_snapshot == second_snapshot


@pytest.mark.parametrize(
    ("configure_env", "expected_message"),
    [
        (
            lambda monkeypatch, database_url: configure_entra_env(monkeypatch, database_url),
            "only supports AUTH_MODE=dev",
        ),
        (
            lambda monkeypatch, database_url: configure_entra_env(
                monkeypatch, database_url, APP_ENV="production"
            ),
            "only runs when APP_ENV is local or test",
        ),
    ],
)
def test_dev_seed_refuses_non_dev_runtime_before_mutations(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
    configure_env,
    expected_message: str,
) -> None:
    run_upgrade(sqlite_db_url)
    configure_env(monkeypatch, sqlite_db_url)
    _refresh_runtime_state()

    with pytest.raises(RuntimeError, match=expected_message):
        dev_seed.main()

    with Session(get_engine()) as session:
        assert session.exec(select(Workspace)).all() == []
        assert session.exec(select(IdentitySubject)).all() == []
        assert session.exec(select(WorkspaceMembership)).all() == []
        assert session.exec(select(AuditEvent)).all() == []
