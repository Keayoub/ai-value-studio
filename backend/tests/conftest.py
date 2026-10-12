from __future__ import annotations

import os
import uuid
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from app.config import clear_settings_cache, get_settings
from app.db.models.identity import IdentitySubject
from app.db.models.lifecycle import (
    Program,
    ProgramAssignmentRole,
    ProgramMember,
    ProgramStatus,
    UseCase,
    UseCaseStatus,
)
from app.db.models.workspace import MembershipStatus, Workspace, WorkspaceMembership
from app.db.session import clear_engine_cache, get_engine
from app.main import create_app
from app.security.auth import clear_jwks_cache
from app.security.roles import ProductRole
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlmodel import Session, select

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"


def _document_storage_root_for(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return str(
            Path(database_url.removeprefix("sqlite:///")).resolve().parent / "document-storage"
        )
    return mkdtemp(prefix="avs-document-storage-")


def make_alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def run_upgrade(database_url: str, revision: str = "head") -> None:
    command.upgrade(make_alembic_config(database_url), revision)


def run_downgrade(database_url: str, revision: str = "base") -> None:
    command.downgrade(make_alembic_config(database_url), revision)


def configure_dev_env(monkeypatch: pytest.MonkeyPatch, database_url: str, **overrides: Any) -> None:
    values = {
        "APP_ENV": "test",
        "AUTH_MODE": "dev",
        "DEBUG": "true",
        "DATABASE_URL": database_url,
        "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:3000,http://localhost:3000",
        "DEV_DEFAULT_SUBJECT": "dev:workspace-admin",
        "DEV_DEFAULT_NAME": "Local Workspace Admin",
        "DEV_USER_ROLE": "WorkspaceAdmin",
        "DEV_WORKSPACE_ID": "",
        "DOCUMENT_STORAGE_PATH": _document_storage_root_for(database_url),
    }
    values.update({key: str(value) for key, value in overrides.items()})
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def configure_entra_env(
    monkeypatch: pytest.MonkeyPatch, database_url: str, **overrides: Any
) -> None:
    values = {
        "APP_ENV": "test",
        "AUTH_MODE": "entra",
        "DEBUG": "false",
        "DATABASE_URL": database_url,
        "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:3000,http://localhost:3000",
        "ENTRA_TENANT_ID": "tenant-123",
        "ENTRA_API_CLIENT_ID": "client-123",
        "ENTRA_API_AUDIENCE": "api://client-123",
        "ENTRA_REQUIRED_SCOPE": "access_as_user",
        "ENTRA_JWKS_CACHE_TTL": "300",
        "ENTRA_JWKS_URL": "https://unit.test/jwks",
        "DOCUMENT_STORAGE_PATH": _document_storage_root_for(database_url),
    }
    values.update({key: str(value) for key, value in overrides.items()})
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def dev_headers(subject_suffix: str, roles: str = "Consultant,WorkspaceAdmin") -> dict[str, str]:
    return {
        "X-Dev-Identity": f"dev:{subject_suffix}",
        "X-Dev-Name": subject_suffix.replace("-", " ").title(),
        "X-Dev-Roles": roles,
    }


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


@pytest.fixture(autouse=True)
def clear_runtime_caches() -> None:
    clear_settings_cache()
    clear_engine_cache()
    clear_jwks_cache()
    yield
    clear_settings_cache()
    clear_engine_cache()
    clear_jwks_cache()


@pytest.fixture
def sqlite_db_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'avs-test.db'}"


@pytest.fixture
def migrated_dev_app(monkeypatch: pytest.MonkeyPatch, sqlite_db_url: str):
    configure_dev_env(monkeypatch, sqlite_db_url)
    run_upgrade(sqlite_db_url)
    return create_app()


@pytest.fixture
def dev_client(migrated_dev_app):
    with TestClient(migrated_dev_app) as client:
        yield client


@pytest.fixture
def postgres_test_urls():
    postgres_source_url = os.getenv("POSTGRES_TEST_URL")
    if not postgres_source_url:
        pytest.skip("POSTGRES_TEST_URL is not configured; skipping PostgreSQL RLS verification.")

    source_url = make_url(postgres_source_url)
    admin_server_url = source_url.set(database="postgres").render_as_string(hide_password=False)
    database_name = f"avs_test_{uuid.uuid4().hex[:8]}"
    role_name = f"avs_app_{uuid.uuid4().hex[:8]}"
    role_password = f"pw_{uuid.uuid4().hex}"

    admin_engine = create_engine(admin_server_url, isolation_level="AUTOCOMMIT")
    quoted_database = _quote_identifier(database_name)
    quoted_role = _quote_identifier(role_name)

    with admin_engine.connect() as connection:
        connection.execute(text(f"CREATE DATABASE {quoted_database}"))

    admin_database_url = source_url.set(database=database_name).render_as_string(
        hide_password=False
    )
    run_upgrade(admin_database_url)

    database_engine = create_engine(admin_database_url)
    with database_engine.begin() as connection:
        connection.execute(
            text(
                f"CREATE ROLE {quoted_role} LOGIN PASSWORD '{role_password}' "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION"
            )
        )
        connection.execute(text(f"GRANT CONNECT ON DATABASE {quoted_database} TO {quoted_role}"))
        connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {quoted_role}"))
        connection.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                f"ON ALL TABLES IN SCHEMA public TO {quoted_role}"
            )
        )

    app_database_url = source_url.set(
        database=database_name,
        username=role_name,
        password=role_password,
    ).render_as_string(hide_password=False)
    try:
        yield {
            "admin_url": admin_database_url,
            "app_url": app_database_url,
            "role_name": role_name,
        }
    finally:
        database_engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.execute(text(f"DROP DATABASE IF EXISTS {quoted_database}"))
            connection.execute(text(f"DROP ROLE IF EXISTS {quoted_role}"))
        admin_engine.dispose()


@pytest.fixture
def postgres_dev_client(monkeypatch: pytest.MonkeyPatch, postgres_test_urls):
    configure_dev_env(monkeypatch, postgres_test_urls["app_url"])
    clear_settings_cache()
    clear_engine_cache()
    assert get_settings().database_url.startswith("postgresql")
    assert get_engine().dialect.name == "postgresql"
    with TestClient(create_app()) as client:
        yield client


def seed_identity(
    session: Session, *, suffix: str, display_name: str | None = None
) -> IdentitySubject:
    identity = session.exec(
        select(IdentitySubject).where(
            IdentitySubject.issuer == "dev",
            IdentitySubject.tenant_id == "dev",
            IdentitySubject.oid == suffix,
        )
    ).first()
    if identity is None:
        identity = IdentitySubject(
            subject=f"dev:{suffix}",
            issuer="dev",
            tenant_id="dev",
            oid=suffix,
            display_name=display_name or suffix.title(),
            email=f"{suffix}@local.dev",
        )
        session.add(identity)
        session.flush()
    return identity


def seed_workspace(
    session: Session,
    *,
    name: str,
    created_by: IdentitySubject,
) -> Workspace:
    workspace = Workspace(
        name=name, description=f"{name} description", created_by_subject_id=created_by.id
    )
    session.add(workspace)
    session.flush()
    return workspace


def seed_membership(
    session: Session,
    *,
    workspace: Workspace,
    identity: IdentitySubject,
    role: ProductRole,
    created_by: IdentitySubject,
    status: MembershipStatus = MembershipStatus.ACTIVE,
) -> WorkspaceMembership:
    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        identity_subject_id=identity.id,
        role=role.value,
        status=status,
        created_by_subject_id=created_by.id,
    )
    session.add(membership)
    session.flush()
    return membership


def seed_program(
    session: Session,
    *,
    workspace: Workspace,
    created_by: IdentitySubject,
    name: str,
    sponsor_membership: WorkspaceMembership | None = None,
    consultant_membership: WorkspaceMembership | None = None,
    status: ProgramStatus = ProgramStatus.DRAFT,
) -> Program:
    program = Program(
        workspace_id=workspace.id,
        name=name,
        strategic_objective=f"{name} objective",
        departments_json=["Operations"],
        sponsor_membership_id=sponsor_membership.id if sponsor_membership else None,
        consultant_membership_id=consultant_membership.id if consultant_membership else None,
        target_use_case_count=3,
        status=status,
        created_by_subject_id=created_by.id,
    )
    session.add(program)
    session.flush()
    return program


def seed_program_member(
    session: Session,
    *,
    workspace: Workspace,
    program: Program,
    membership: WorkspaceMembership,
    assignment_role: ProgramAssignmentRole,
    created_by: IdentitySubject,
) -> ProgramMember:
    program_member = ProgramMember(
        workspace_id=workspace.id,
        program_id=program.id,
        membership_id=membership.id,
        assignment_role=assignment_role,
        created_by_subject_id=created_by.id,
    )
    session.add(program_member)
    session.flush()
    return program_member


def seed_use_case(
    session: Session,
    *,
    workspace: Workspace,
    program: Program,
    created_by: IdentitySubject,
    title: str,
    owner_membership: WorkspaceMembership | None = None,
    status: UseCaseStatus = UseCaseStatus.DRAFT,
) -> UseCase:
    use_case = UseCase(
        workspace_id=workspace.id,
        program_id=program.id,
        title=title,
        department="Operations",
        owner_membership_id=owner_membership.id if owner_membership else None,
        status=status,
        created_by_subject_id=created_by.id,
    )
    session.add(use_case)
    session.flush()
    return use_case


@pytest.fixture
def seeded_workspace_data(monkeypatch: pytest.MonkeyPatch, sqlite_db_url: str) -> dict[str, object]:
    configure_dev_env(monkeypatch, sqlite_db_url)
    run_upgrade(sqlite_db_url)

    with Session(get_engine()) as session:
        actor = seed_identity(session, suffix="actor", display_name="Actor Admin")
        outsider = seed_identity(session, suffix="outsider", display_name="Outsider Admin")
        target_a = seed_identity(session, suffix="member-a", display_name="Member A")
        target_b = seed_identity(session, suffix="member-b", display_name="Member B")

        workspace_a = seed_workspace(session, name="Workspace A", created_by=actor)
        workspace_b = seed_workspace(session, name="Workspace B", created_by=outsider)

        actor_membership = seed_membership(
            session,
            workspace=workspace_a,
            identity=actor,
            role=ProductRole.WORKSPACE_ADMIN,
            created_by=actor,
        )
        target_a_membership = seed_membership(
            session,
            workspace=workspace_a,
            identity=target_a,
            role=ProductRole.CONTRIBUTOR,
            created_by=actor,
        )
        outsider_membership = seed_membership(
            session,
            workspace=workspace_b,
            identity=outsider,
            role=ProductRole.WORKSPACE_ADMIN,
            created_by=outsider,
        )
        target_b_membership = seed_membership(
            session,
            workspace=workspace_b,
            identity=target_b,
            role=ProductRole.CONTRIBUTOR,
            created_by=outsider,
        )
        disabled_workspace = seed_workspace(session, name="Disabled Workspace", created_by=actor)
        disabled_membership = seed_membership(
            session,
            workspace=disabled_workspace,
            identity=actor,
            role=ProductRole.WORKSPACE_ADMIN,
            created_by=actor,
            status=MembershipStatus.DISABLED,
        )
        session.commit()

        return {
            "workspace_a_id": workspace_a.id,
            "workspace_b_id": workspace_b.id,
            "disabled_workspace_id": disabled_workspace.id,
            "actor_membership_id": actor_membership.id,
            "target_a_membership_id": target_a_membership.id,
            "outsider_membership_id": outsider_membership.id,
            "target_b_membership_id": target_b_membership.id,
            "disabled_membership_id": disabled_membership.id,
        }


@pytest.fixture
def seeded_lifecycle_data(monkeypatch: pytest.MonkeyPatch, sqlite_db_url: str) -> dict[str, object]:
    configure_dev_env(monkeypatch, sqlite_db_url)
    run_upgrade(sqlite_db_url)

    with Session(get_engine()) as session:
        admin_a = seed_identity(session, suffix="admin-a", display_name="Workspace Admin A")
        consultant_a = seed_identity(session, suffix="consultant-a", display_name="Consultant A")
        sponsor_a = seed_identity(session, suffix="sponsor-a", display_name="Sponsor A")
        sponsor_unassigned_a = seed_identity(
            session,
            suffix="sponsor-unassigned-a",
            display_name="Unassigned Sponsor A",
        )
        contributor_a = seed_identity(session, suffix="contributor-a", display_name="Contributor A")
        extra_a = seed_identity(session, suffix="extra-a", display_name="Extra A")
        admin_b = seed_identity(session, suffix="admin-b", display_name="Workspace Admin B")
        contributor_b = seed_identity(session, suffix="contributor-b", display_name="Contributor B")

        workspace_a = seed_workspace(session, name="Workspace A", created_by=admin_a)
        workspace_b = seed_workspace(session, name="Workspace B", created_by=admin_b)

        admin_a_membership = seed_membership(
            session,
            workspace=workspace_a,
            identity=admin_a,
            role=ProductRole.WORKSPACE_ADMIN,
            created_by=admin_a,
        )
        consultant_a_membership = seed_membership(
            session,
            workspace=workspace_a,
            identity=consultant_a,
            role=ProductRole.CONSULTANT,
            created_by=admin_a,
        )
        sponsor_a_membership = seed_membership(
            session,
            workspace=workspace_a,
            identity=sponsor_a,
            role=ProductRole.SPONSOR,
            created_by=admin_a,
        )
        sponsor_unassigned_a_membership = seed_membership(
            session,
            workspace=workspace_a,
            identity=sponsor_unassigned_a,
            role=ProductRole.SPONSOR,
            created_by=admin_a,
        )
        contributor_a_membership = seed_membership(
            session,
            workspace=workspace_a,
            identity=contributor_a,
            role=ProductRole.CONTRIBUTOR,
            created_by=admin_a,
        )
        extra_a_membership = seed_membership(
            session,
            workspace=workspace_a,
            identity=extra_a,
            role=ProductRole.CONTRIBUTOR,
            created_by=admin_a,
        )
        admin_b_membership = seed_membership(
            session,
            workspace=workspace_b,
            identity=admin_b,
            role=ProductRole.WORKSPACE_ADMIN,
            created_by=admin_b,
        )
        contributor_b_membership = seed_membership(
            session,
            workspace=workspace_b,
            identity=contributor_b,
            role=ProductRole.CONTRIBUTOR,
            created_by=admin_b,
        )

        program_a = seed_program(
            session,
            workspace=workspace_a,
            created_by=consultant_a,
            name="Programme A",
            sponsor_membership=sponsor_a_membership,
            consultant_membership=consultant_a_membership,
        )
        seed_program_member(
            session,
            workspace=workspace_a,
            program=program_a,
            membership=contributor_a_membership,
            assignment_role=ProgramAssignmentRole.CONTRIBUTOR,
            created_by=admin_a,
        )
        seed_program_member(
            session,
            workspace=workspace_a,
            program=program_a,
            membership=sponsor_unassigned_a_membership,
            assignment_role=ProgramAssignmentRole.SPONSOR,
            created_by=admin_a,
        )
        use_case_a = seed_use_case(
            session,
            workspace=workspace_a,
            program=program_a,
            created_by=consultant_a,
            title="Use Case A",
            owner_membership=contributor_a_membership,
        )
        other_use_case_a = seed_use_case(
            session,
            workspace=workspace_a,
            program=program_a,
            created_by=consultant_a,
            title="Use Case A2",
            owner_membership=sponsor_unassigned_a_membership,
        )

        program_b = seed_program(
            session,
            workspace=workspace_b,
            created_by=admin_b,
            name="Programme B",
            sponsor_membership=None,
            consultant_membership=None,
        )
        seed_program_member(
            session,
            workspace=workspace_b,
            program=program_b,
            membership=contributor_b_membership,
            assignment_role=ProgramAssignmentRole.CONTRIBUTOR,
            created_by=admin_b,
        )
        use_case_b = seed_use_case(
            session,
            workspace=workspace_b,
            program=program_b,
            created_by=admin_b,
            title="Use Case B",
            owner_membership=contributor_b_membership,
        )
        session.commit()

        return {
            "workspace_a_id": workspace_a.id,
            "workspace_b_id": workspace_b.id,
            "program_a_id": program_a.id,
            "program_b_id": program_b.id,
            "use_case_a_id": use_case_a.id,
            "other_use_case_a_id": other_use_case_a.id,
            "use_case_b_id": use_case_b.id,
            "admin_a_membership_id": admin_a_membership.id,
            "consultant_a_membership_id": consultant_a_membership.id,
            "sponsor_a_membership_id": sponsor_a_membership.id,
            "sponsor_unassigned_a_membership_id": sponsor_unassigned_a_membership.id,
            "contributor_a_membership_id": contributor_a_membership.id,
            "extra_a_membership_id": extra_a_membership.id,
            "contributor_b_membership_id": contributor_b_membership.id,
            "admin_b_membership_id": admin_b_membership.id,
        }
