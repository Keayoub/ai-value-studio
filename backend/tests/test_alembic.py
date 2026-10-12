from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from backend.tests.conftest import run_downgrade, run_upgrade


def test_sqlite_alembic_upgrade_and_downgrade(sqlite_db_url: str) -> None:
    run_upgrade(sqlite_db_url)
    engine = create_engine(sqlite_db_url)

    inspector = inspect(engine)
    assert {
        "identity_subjects",
        "workspaces",
        "workspace_memberships",
        "audit_events",
        "programs",
        "program_members",
        "use_cases",
        "questionnaire_template_versions",
        "question_definitions",
        "assessment_versions",
        "answers",
        "hypotheses",
        "reviews",
        "review_comments",
        "approvals",
        "documents",
        "document_versions",
    } <= set(inspector.get_table_names())
    audit_columns = {column["name"] for column in inspector.get_columns("audit_events")}
    assert {"before_hash", "after_hash", "metadata_json"} <= audit_columns
    assert "before_json" not in audit_columns
    assert "after_json" not in audit_columns
    program_columns = {column["name"] for column in inspector.get_columns("programs")}
    use_case_columns = {column["name"] for column in inspector.get_columns("use_cases")}
    template_columns = {
        column["name"] for column in inspector.get_columns("questionnaire_template_versions")
    }
    assessment_columns = {column["name"] for column in inspector.get_columns("assessment_versions")}
    review_columns = {column["name"] for column in inspector.get_columns("reviews")}
    approval_columns = {column["name"] for column in inspector.get_columns("approvals")}
    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    document_version_columns = {
        column["name"] for column in inspector.get_columns("document_versions")
    }
    assert {"sponsor_membership_id", "consultant_membership_id", "status"} <= program_columns
    assert {"owner_membership_id", "submitted_at", "approved_at"} <= use_case_columns
    assert {"template_key", "version", "schema_json"} <= template_columns
    assert {
        "template_version_id",
        "snapshot_json",
        "respondent_membership_id",
        "approved_by_subject_id",
        "approved_at",
    } <= assessment_columns
    assert {"recommendation", "summary", "risks_json", "decision_reason"} <= review_columns
    assert {
        "decision",
        "decision_reason",
        "idempotency_key",
        "response_snapshot_json",
    } <= approval_columns
    assert {"type", "language", "status", "current_version_no"} <= document_columns
    assert {
        "format",
        "storage_key",
        "sha256",
        "source_snapshot_json",
        "ai_assisted_sections_json",
        "idempotency_key",
    } <= document_version_columns

    with engine.begin() as connection:
        seeded_template = (
            connection.execute(
                text(
                    """
                SELECT template_key, version, locale
                FROM questionnaire_template_versions
                WHERE template_key = 'baseline-fr'
                """
                )
            )
            .mappings()
            .one()
        )
        question_count = connection.execute(
            text("SELECT COUNT(*) FROM question_definitions")
        ).scalar_one()
    assert seeded_template == {
        "template_key": "baseline-fr",
        "version": 1,
        "locale": "fr",
    }
    assert question_count >= 40

    run_downgrade(sqlite_db_url)
    downgraded_inspector = inspect(engine)
    assert "workspaces" not in downgraded_inspector.get_table_names()


def test_postgres_rls_policies_enforce_real_row_isolation(postgres_test_urls) -> None:
    admin_engine = create_engine(postgres_test_urls["admin_url"])
    app_engine = create_engine(postgres_test_urls["app_url"])

    actor_id = uuid.uuid4()
    actor_workspace_id = uuid.uuid4()
    target_member_id = uuid.uuid4()
    outsider_id = uuid.uuid4()
    outsider_workspace_id = uuid.uuid4()

    with admin_engine.begin() as connection:
        role_row = connection.execute(
            text("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = :role_name"),
            {"role_name": postgres_test_urls["role_name"]},
        ).one()
        policies = connection.execute(
            text(
                """
                SELECT tablename, policyname
                FROM pg_policies
                WHERE schemaname = current_schema()
                  AND tablename IN (
                      'workspaces',
                      'workspace_memberships',
                      'audit_events',
                      'programs',
                      'program_members',
                      'use_cases',
                      'assessment_versions',
                      'reviews',
                      'review_comments',
                      'approvals'
                  )
                ORDER BY tablename, policyname
                """
            )
        ).all()
        row_security = connection.execute(
            text(
                """
                SELECT relname, relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname IN (
                    'workspaces',
                    'workspace_memberships',
                    'audit_events',
                    'programs',
                    'program_members',
                    'use_cases',
                    'assessment_versions',
                    'reviews',
                    'review_comments',
                    'approvals'
                )
                ORDER BY relname
                """
            )
        ).all()
        connection.execute(
            text(
                """
                INSERT INTO identity_subjects
                    (
                        id,
                        subject,
                        issuer,
                        tenant_id,
                        oid,
                        display_name,
                        email,
                        created_at,
                        updated_at
                    )
                VALUES
                    (
                        :actor_id,
                        'dev:actor',
                        'dev',
                        'dev',
                        'actor',
                        'Actor',
                        'actor@local.dev',
                        now(),
                        now()
                    ),
                    (
                        :target_member_id,
                        'dev:member-a',
                        'dev',
                        'dev',
                        'member-a',
                        'Member A',
                        'member-a@local.dev',
                        now(),
                        now()
                    ),
                    (
                        :outsider_id,
                        'dev:outsider',
                        'dev',
                        'dev',
                        'outsider',
                        'Outsider',
                        'outsider@local.dev',
                        now(),
                        now()
                    )
                """
            ),
            {
                "actor_id": actor_id,
                "target_member_id": target_member_id,
                "outsider_id": outsider_id,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO workspaces
                    (
                        id,
                        name,
                        sector,
                        country_region,
                        size_band,
                        default_language,
                        description,
                        branding_json,
                        confidentiality_policy,
                        status,
                        created_by_subject_id,
                        created_at,
                        updated_at
                    )
                VALUES
                    (
                        :actor_workspace_id,
                        'Workspace A',
                        'Public sector',
                        'CA-QC',
                        'enterprise',
                        'fr-CA',
                        'Workspace A description',
                        CAST(:branding_json AS json),
                        'restricted',
                        'ACTIVE',
                        :actor_id,
                        now(),
                        now()
                    ),
                    (
                        :outsider_workspace_id,
                        'Workspace B',
                        'Industry',
                        'US-NY',
                        'small',
                        'en',
                        'Workspace B description',
                        CAST(:branding_json AS json),
                        'internal-only',
                        'ACTIVE',
                        :outsider_id,
                        now(),
                        now()
                    )
                """
            ),
            {
                "actor_workspace_id": actor_workspace_id,
                "outsider_workspace_id": outsider_workspace_id,
                "actor_id": actor_id,
                "outsider_id": outsider_id,
                "branding_json": '{"primary_color":"#112233"}',
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO workspace_memberships
                    (
                        id,
                        workspace_id,
                        identity_subject_id,
                        role,
                        status,
                        created_by_subject_id,
                        created_at,
                        updated_at
                    )
                VALUES
                    (
                        :membership_a,
                        :actor_workspace_id,
                        :actor_id,
                        'WorkspaceAdmin',
                        'ACTIVE',
                        :actor_id,
                        now(),
                        now()
                    ),
                    (
                        :membership_target,
                        :actor_workspace_id,
                        :target_member_id,
                        'Contributor',
                        'ACTIVE',
                        :actor_id,
                        now(),
                        now()
                    ),
                    (
                        :membership_b,
                        :outsider_workspace_id,
                        :outsider_id,
                        'WorkspaceAdmin',
                        'ACTIVE',
                        :outsider_id,
                        now(),
                        now()
                    )
                """
            ),
            {
                "membership_a": uuid.uuid4(),
                "membership_target": uuid.uuid4(),
                "membership_b": uuid.uuid4(),
                "actor_workspace_id": actor_workspace_id,
                "actor_id": actor_id,
                "target_member_id": target_member_id,
                "outsider_workspace_id": outsider_workspace_id,
                "outsider_id": outsider_id,
            },
        )

    assert not role_row.rolbypassrls
    assert not role_row.rolsuper
    assert len(policies) == 10
    assert all(row.relrowsecurity and row.relforcerowsecurity for row in row_security)

    with app_engine.begin() as connection:
        connection.execute(
            text("SELECT set_config('app.identity_subject_id', :actor_id, true)"),
            {"actor_id": str(actor_id)},
        )
        visible_membership_count = connection.execute(
            text("SELECT count(*) FROM workspace_memberships")
        ).scalar_one()
        visible_workspace_ids = (
            connection.execute(text("SELECT id FROM workspaces ORDER BY name")).scalars().all()
        )

        connection.execute(
            text("SELECT set_config('app.workspace_id', :workspace_id, true)"),
            {"workspace_id": str(actor_workspace_id)},
        )
        preverification_membership_count = connection.execute(
            text("SELECT count(*) FROM workspace_memberships WHERE workspace_id = :workspace_id"),
            {"workspace_id": actor_workspace_id},
        ).scalar_one()
        connection.execute(text("SELECT set_config('app.workspace_access_verified', 'true', true)"))
        scoped_membership_count = connection.execute(
            text("SELECT count(*) FROM workspace_memberships WHERE workspace_id = :workspace_id"),
            {"workspace_id": actor_workspace_id},
        ).scalar_one()
        cross_workspace_count = connection.execute(
            text("SELECT count(*) FROM workspace_memberships WHERE workspace_id = :workspace_id"),
            {"workspace_id": outsider_workspace_id},
        ).scalar_one()
        blocked_update_count = connection.execute(
            text("UPDATE workspaces SET name = 'Not Allowed' WHERE id = :workspace_id"),
            {"workspace_id": outsider_workspace_id},
        ).rowcount

        with pytest.raises(SQLAlchemyError):
            connection.execute(
                text(
                    """
                    INSERT INTO workspace_memberships
                        (
                            id,
                            workspace_id,
                            identity_subject_id,
                            role,
                            status,
                            created_by_subject_id,
                            created_at,
                            updated_at
                        )
                    VALUES
                        (:membership_id, :workspace_id, :identity_subject_id, 'Contributor',
                         'ACTIVE', :created_by_subject_id, now(), now())
                    """
                ),
                {
                    "membership_id": uuid.uuid4(),
                    "workspace_id": outsider_workspace_id,
                    "identity_subject_id": actor_id,
                    "created_by_subject_id": actor_id,
                },
            )

    assert visible_membership_count == 1
    assert visible_workspace_ids == [actor_workspace_id]
    assert preverification_membership_count == 1
    assert scoped_membership_count == 2
    assert cross_workspace_count == 0
    assert blocked_update_count == 0
