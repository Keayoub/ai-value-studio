"""Add S5 value assessment and scorecard tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261012_0005"
down_revision = "20261011_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "value_assessments",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("use_case_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("annual_volume", sa.Numeric(18, 2), nullable=False),
        sa.Column("time_saved_hours", sa.Numeric(18, 4), nullable=False),
        sa.Column("hourly_cost", sa.Numeric(18, 2), nullable=False),
        sa.Column("error_reduction_rate", sa.Numeric(10, 4), nullable=False),
        sa.Column("average_error_cost", sa.Numeric(18, 2), nullable=False),
        sa.Column("revenue_capacity_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("estimated_annual_cost", sa.Numeric(18, 2), nullable=False),
        sa.Column("time_to_impact_months", sa.Integer(), nullable=False),
        sa.Column("primary_kpi", sa.String(length=255), nullable=False),
        sa.Column("kpi_target", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("calculation_version", sa.String(length=32), nullable=False),
        sa.Column("annual_time_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("error_avoidance_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("gross_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("net_annual_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("npv_3y", sa.Numeric(18, 2), nullable=False),
        sa.Column("payback_months", sa.Numeric(10, 2), nullable=True),
        sa.Column("input_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("source_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("scenarios_json", sa.JSON(), nullable=False),
        sa.Column("sensitivities_json", sa.JSON(), nullable=False),
        sa.Column("created_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assessment_version_id"], ["assessment_versions.id"]),
        sa.ForeignKeyConstraint(["created_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["use_case_id"], ["use_cases.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assessment_version_id",
            "revision",
            name="uq_value_assessment_assessment_version",
        ),
    )
    op.create_index(
        op.f("ix_value_assessments_workspace_id"),
        "value_assessments",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_value_assessments_use_case_id"),
        "value_assessments",
        ["use_case_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_value_assessments_assessment_version_id"),
        "value_assessments",
        ["assessment_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_value_assessments_created_by_subject_id"),
        "value_assessments",
        ["created_by_subject_id"],
        unique=False,
    )

    op.create_table(
        "score_configuration_versions",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("weights_json", sa.JSON(), nullable=False),
        sa.Column("thresholds_json", sa.JSON(), nullable=False),
        sa.Column("created_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "version",
            name="uq_score_configuration_workspace_version",
        ),
    )
    op.create_index(
        op.f("ix_score_configuration_versions_workspace_id"),
        "score_configuration_versions",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_score_configuration_versions_created_by_subject_id"),
        "score_configuration_versions",
        ["created_by_subject_id"],
        unique=False,
    )

    op.create_table(
        "scorecard_versions",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("use_case_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("value_assessment_id", sa.Uuid(), nullable=False),
        sa.Column("score_configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("priority_score", sa.Numeric(8, 3), nullable=False),
        sa.Column("readiness_average", sa.Numeric(8, 3), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("risk_profile", sa.String(length=16), nullable=False),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("calculation_version", sa.String(length=32), nullable=False),
        sa.Column("manual_override", sa.Boolean(), nullable=False),
        sa.Column("override_reason", sa.String(length=2000), nullable=True),
        sa.Column("input_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("formula_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assessment_version_id"], ["assessment_versions.id"]),
        sa.ForeignKeyConstraint(["created_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(
            ["score_configuration_version_id"], ["score_configuration_versions.id"]
        ),
        sa.ForeignKeyConstraint(["use_case_id"], ["use_cases.id"]),
        sa.ForeignKeyConstraint(["value_assessment_id"], ["value_assessments.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("use_case_id", "version", name="uq_scorecard_use_case_version"),
    )
    op.create_index(
        op.f("ix_scorecard_versions_workspace_id"),
        "scorecard_versions",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scorecard_versions_use_case_id"),
        "scorecard_versions",
        ["use_case_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scorecard_versions_assessment_version_id"),
        "scorecard_versions",
        ["assessment_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scorecard_versions_value_assessment_id"),
        "scorecard_versions",
        ["value_assessment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scorecard_versions_score_configuration_version_id"),
        "scorecard_versions",
        ["score_configuration_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scorecard_versions_created_by_subject_id"),
        "scorecard_versions",
        ["created_by_subject_id"],
        unique=False,
    )

    op.create_table(
        "dimension_scores",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("scorecard_version_id", sa.Uuid(), nullable=False),
        sa.Column("dimension", sa.String(length=64), nullable=False),
        sa.Column("weight", sa.Numeric(8, 4), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("justification", sa.String(length=2000), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("is_manual_override", sa.Boolean(), nullable=False),
        sa.Column("override_reason", sa.String(length=2000), nullable=True),
        sa.Column("created_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["scorecard_version_id"], ["scorecard_versions.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scorecard_version_id",
            "dimension",
            name="uq_dimension_score_scorecard_dimension",
        ),
    )
    op.create_index(
        op.f("ix_dimension_scores_workspace_id"),
        "dimension_scores",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dimension_scores_scorecard_version_id"),
        "dimension_scores",
        ["scorecard_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dimension_scores_created_by_subject_id"),
        "dimension_scores",
        ["created_by_subject_id"],
        unique=False,
    )

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    table_names = (
        "value_assessments",
        "score_configuration_versions",
        "scorecard_versions",
        "dimension_scores",
    )
    current_workspace = "nullif(current_setting('app.workspace_id', true), '')::uuid"
    scoped_tenant = (
        f"workspace_id = {current_workspace} "
        "AND current_setting('app.workspace_access_verified', true) = 'true'"
    )
    for table_name in table_names:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table_name}_workspace_scope ON {table_name} "
            f"USING ({scoped_tenant}) WITH CHECK ({scoped_tenant})"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in (
            "dimension_scores",
            "scorecard_versions",
            "score_configuration_versions",
            "value_assessments",
        ):
            op.execute(f"DROP POLICY IF EXISTS {table_name}_workspace_scope ON {table_name}")
            op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")

    op.drop_index(op.f("ix_dimension_scores_created_by_subject_id"), table_name="dimension_scores")
    op.drop_index(op.f("ix_dimension_scores_scorecard_version_id"), table_name="dimension_scores")
    op.drop_index(op.f("ix_dimension_scores_workspace_id"), table_name="dimension_scores")
    op.drop_table("dimension_scores")

    op.drop_index(
        op.f("ix_scorecard_versions_created_by_subject_id"),
        table_name="scorecard_versions",
    )
    op.drop_index(
        op.f("ix_scorecard_versions_score_configuration_version_id"),
        table_name="scorecard_versions",
    )
    op.drop_index(
        op.f("ix_scorecard_versions_value_assessment_id"),
        table_name="scorecard_versions",
    )
    op.drop_index(
        op.f("ix_scorecard_versions_assessment_version_id"),
        table_name="scorecard_versions",
    )
    op.drop_index(op.f("ix_scorecard_versions_use_case_id"), table_name="scorecard_versions")
    op.drop_index(op.f("ix_scorecard_versions_workspace_id"), table_name="scorecard_versions")
    op.drop_table("scorecard_versions")

    op.drop_index(
        op.f("ix_score_configuration_versions_created_by_subject_id"),
        table_name="score_configuration_versions",
    )
    op.drop_index(
        op.f("ix_score_configuration_versions_workspace_id"),
        table_name="score_configuration_versions",
    )
    op.drop_table("score_configuration_versions")

    op.drop_index(
        op.f("ix_value_assessments_created_by_subject_id"), table_name="value_assessments"
    )
    op.drop_index(op.f("ix_value_assessments_assessment_version_id"), table_name="value_assessments")
    op.drop_index(op.f("ix_value_assessments_use_case_id"), table_name="value_assessments")
    op.drop_index(op.f("ix_value_assessments_workspace_id"), table_name="value_assessments")
    op.drop_table("value_assessments")
