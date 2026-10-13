"""Add persisted S4 wizard tables and seed baseline template."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table


revision = "20261011_0004"
down_revision = "20261011_0003"
branch_labels = None
depends_on = None


def _template_payload() -> dict[str, object]:
    template_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "wizard"
        / "templates"
        / "baseline_fr.yaml"
    )
    return json.loads(template_path.read_text(encoding="utf-8"))


def _question_rows(
    *,
    template_id: uuid.UUID,
    now: datetime,
    payload: dict[str, object],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    steps = payload.get("steps", [])
    if not isinstance(steps, list):
        return rows

    for step in steps:
        if not isinstance(step, dict):
            continue
        step_index = int(step["index"])
        questions = step.get("questions", [])
        if not isinstance(questions, list):
            continue
        for sort_order, question in enumerate(questions, start=1):
            if not isinstance(question, dict):
                continue
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "template_version_id": template_id,
                    "step_index": step_index,
                    "sort_order": sort_order,
                    "question_key": str(question["key"]),
                    "field_type": str(question["field_type"]),
                    "label": str(question["label"]),
                    "help_text": question.get("help_text"),
                    "placeholder": question.get("placeholder"),
                    "options_json": question.get("options") or None,
                    "schema_json": question.get("schema") or {},
                    "conditional_json": {
                        "visible_if": question.get("visible_if", []),
                        "required_if": question.get("required_if", []),
                    },
                    "ui_json": {"required": bool(question.get("required", False))},
                    "contributor_editable": bool(question.get("contributor_editable", True)),
                    "created_at": now,
                    "updated_at": now,
                }
            )
    return rows


def _drop_policies(table_names: Iterable[str]) -> None:
    for table_name in table_names:
        op.execute(f"DROP POLICY IF EXISTS {table_name}_workspace_scope ON {table_name}")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.create_table(
        "questionnaire_template_versions",
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("template_key", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("created_by_subject_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "template_key",
            "version",
            name="uq_questionnaire_template_workspace_key_version",
        ),
    )
    op.create_index(
        op.f("ix_questionnaire_template_versions_workspace_id"),
        "questionnaire_template_versions",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_questionnaire_template_versions_template_key"),
        "questionnaire_template_versions",
        ["template_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_questionnaire_template_versions_created_by_subject_id"),
        "questionnaire_template_versions",
        ["created_by_subject_id"],
        unique=False,
    )

    op.create_table(
        "question_definitions",
        sa.Column("template_version_id", sa.Uuid(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("question_key", sa.String(length=120), nullable=False),
        sa.Column("field_type", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("help_text", sa.String(length=2000), nullable=True),
        sa.Column("placeholder", sa.String(length=300), nullable=True),
        sa.Column("options_json", sa.JSON(), nullable=True),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("conditional_json", sa.JSON(), nullable=True),
        sa.Column("ui_json", sa.JSON(), nullable=True),
        sa.Column("contributor_editable", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["questionnaire_template_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_version_id",
            "question_key",
            name="uq_question_definition_template_question_key",
        ),
    )
    op.create_index(
        op.f("ix_question_definitions_template_version_id"),
        "question_definitions",
        ["template_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_question_definitions_step_index"),
        "question_definitions",
        ["step_index"],
        unique=False,
    )

    op.create_table(
        "assessment_versions",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("use_case_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("template_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("interview_mode", sa.Boolean(), nullable=False),
        sa.Column("respondent_membership_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_json", sa.JSON(), nullable=True),
        sa.Column("submitted_by_subject_id", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["respondent_membership_id"], ["workspace_memberships.id"]),
        sa.ForeignKeyConstraint(["submitted_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["template_version_id"], ["questionnaire_template_versions.id"]),
        sa.ForeignKeyConstraint(["use_case_id"], ["use_cases.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "use_case_id",
            "version",
            name="uq_assessment_version_use_case_version",
        ),
    )
    op.create_index(
        op.f("ix_assessment_versions_workspace_id"),
        "assessment_versions",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assessment_versions_use_case_id"),
        "assessment_versions",
        ["use_case_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assessment_versions_template_version_id"),
        "assessment_versions",
        ["template_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assessment_versions_respondent_membership_id"),
        "assessment_versions",
        ["respondent_membership_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assessment_versions_submitted_by_subject_id"),
        "assessment_versions",
        ["submitted_by_subject_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assessment_versions_created_by_subject_id"),
        "assessment_versions",
        ["created_by_subject_id"],
        unique=False,
    )

    op.create_table(
        "answers",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("question_key", sa.String(length=120), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("evidence_text", sa.String(length=2000), nullable=True),
        sa.Column("confidence", sa.String(length=120), nullable=True),
        sa.Column("entered_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("captured_for_membership_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assessment_version_id"], ["assessment_versions.id"]),
        sa.ForeignKeyConstraint(["captured_for_membership_id"], ["workspace_memberships.id"]),
        sa.ForeignKeyConstraint(["entered_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assessment_version_id",
            "question_key",
            name="uq_answer_assessment_question_key",
        ),
    )
    op.create_index(op.f("ix_answers_workspace_id"), "answers", ["workspace_id"], unique=False)
    op.create_index(
        op.f("ix_answers_assessment_version_id"),
        "answers",
        ["assessment_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_answers_entered_by_subject_id"),
        "answers",
        ["entered_by_subject_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_answers_captured_for_membership_id"),
        "answers",
        ["captured_for_membership_id"],
        unique=False,
    )

    op.create_table(
        "hypotheses",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("use_case_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("statement", sa.String(length=2000), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("evidence_ref", sa.String(length=255), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assessment_version_id"], ["assessment_versions.id"]),
        sa.ForeignKeyConstraint(["use_case_id"], ["use_cases.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_hypotheses_workspace_id"),
        "hypotheses",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_hypotheses_use_case_id"),
        "hypotheses",
        ["use_case_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_hypotheses_assessment_version_id"),
        "hypotheses",
        ["assessment_version_id"],
        unique=False,
    )

    now = datetime.now(UTC)
    template_id = uuid.uuid4()
    payload = _template_payload()

    template_versions_table = table(
        "questionnaire_template_versions",
        sa.Column("id", sa.Uuid()),
        sa.Column("workspace_id", sa.Uuid()),
        sa.Column("template_key", sa.String()),
        sa.Column("version", sa.Integer()),
        sa.Column("locale", sa.String()),
        sa.Column("title", sa.String()),
        sa.Column("description", sa.String()),
        sa.Column("is_active", sa.Boolean()),
        sa.Column("schema_json", sa.JSON()),
        sa.Column("created_by_subject_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    question_definitions_table = table(
        "question_definitions",
        sa.Column("id", sa.Uuid()),
        sa.Column("template_version_id", sa.Uuid()),
        sa.Column("step_index", sa.Integer()),
        sa.Column("sort_order", sa.Integer()),
        sa.Column("question_key", sa.String()),
        sa.Column("field_type", sa.String()),
        sa.Column("label", sa.String()),
        sa.Column("help_text", sa.String()),
        sa.Column("placeholder", sa.String()),
        sa.Column("options_json", sa.JSON()),
        sa.Column("schema_json", sa.JSON()),
        sa.Column("conditional_json", sa.JSON()),
        sa.Column("ui_json", sa.JSON()),
        sa.Column("contributor_editable", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        template_versions_table,
        [
            {
                "id": template_id,
                "workspace_id": None,
                "template_key": str(payload["template_key"]),
                "version": int(payload["version"]),
                "locale": str(payload["locale"]),
                "title": str(payload["title"]),
                "description": payload.get("description"),
                "is_active": True,
                "schema_json": payload,
                "created_by_subject_id": None,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.bulk_insert(
        question_definitions_table,
        _question_rows(template_id=template_id, now=now, payload=payload),
    )

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    tenant_tables = [
        "questionnaire_template_versions",
        "assessment_versions",
        "answers",
        "hypotheses",
    ]
    for table_name in tenant_tables:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")

    current_workspace = "nullif(current_setting('app.workspace_id', true), '')::uuid"
    scoped_tenant = (
        f"workspace_id = {current_workspace} "
        "AND current_setting('app.workspace_access_verified', true) = 'true'"
    )
    template_scope = (
        f"((workspace_id IS NULL) OR workspace_id = {current_workspace}) "
        "AND current_setting('app.workspace_access_verified', true) = 'true'"
    )

    op.execute(
        "CREATE POLICY questionnaire_template_versions_workspace_scope "
        "ON questionnaire_template_versions "
        f"USING ({template_scope}) WITH CHECK ({scoped_tenant})"
    )
    op.execute(
        "CREATE POLICY assessment_versions_workspace_scope ON assessment_versions "
        f"USING ({scoped_tenant}) WITH CHECK ({scoped_tenant})"
    )
    op.execute(
        "CREATE POLICY answers_workspace_scope ON answers "
        f"USING ({scoped_tenant}) WITH CHECK ({scoped_tenant})"
    )
    op.execute(
        "CREATE POLICY hypotheses_workspace_scope ON hypotheses "
        f"USING ({scoped_tenant}) WITH CHECK ({scoped_tenant})"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _drop_policies(
            [
                "hypotheses",
                "answers",
                "assessment_versions",
                "questionnaire_template_versions",
            ]
        )

    op.drop_index(op.f("ix_hypotheses_assessment_version_id"), table_name="hypotheses")
    op.drop_index(op.f("ix_hypotheses_use_case_id"), table_name="hypotheses")
    op.drop_index(op.f("ix_hypotheses_workspace_id"), table_name="hypotheses")
    op.drop_table("hypotheses")

    op.drop_index(op.f("ix_answers_captured_for_membership_id"), table_name="answers")
    op.drop_index(op.f("ix_answers_entered_by_subject_id"), table_name="answers")
    op.drop_index(op.f("ix_answers_assessment_version_id"), table_name="answers")
    op.drop_index(op.f("ix_answers_workspace_id"), table_name="answers")
    op.drop_table("answers")

    op.drop_index(op.f("ix_assessment_versions_created_by_subject_id"), table_name="assessment_versions")
    op.drop_index(op.f("ix_assessment_versions_submitted_by_subject_id"), table_name="assessment_versions")
    op.drop_index(op.f("ix_assessment_versions_respondent_membership_id"), table_name="assessment_versions")
    op.drop_index(op.f("ix_assessment_versions_template_version_id"), table_name="assessment_versions")
    op.drop_index(op.f("ix_assessment_versions_use_case_id"), table_name="assessment_versions")
    op.drop_index(op.f("ix_assessment_versions_workspace_id"), table_name="assessment_versions")
    op.drop_table("assessment_versions")

    op.drop_index(op.f("ix_question_definitions_step_index"), table_name="question_definitions")
    op.drop_index(op.f("ix_question_definitions_template_version_id"), table_name="question_definitions")
    op.drop_table("question_definitions")

    op.drop_index(
        op.f("ix_questionnaire_template_versions_created_by_subject_id"),
        table_name="questionnaire_template_versions",
    )
    op.drop_index(
        op.f("ix_questionnaire_template_versions_template_key"),
        table_name="questionnaire_template_versions",
    )
    op.drop_index(
        op.f("ix_questionnaire_template_versions_workspace_id"),
        table_name="questionnaire_template_versions",
    )
    op.drop_table("questionnaire_template_versions")
