"""Add program and use-case lifecycle tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261011_0003"
down_revision = "20261011_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "programs",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("strategic_objective", sa.String(length=2000), nullable=True),
        sa.Column("departments_json", sa.JSON(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("sponsor_membership_id", sa.Uuid(), nullable=True),
        sa.Column("consultant_membership_id", sa.Uuid(), nullable=True),
        sa.Column("target_use_case_count", sa.Integer(), nullable=True),
        sa.Column("questionnaire_template_version_id", sa.Uuid(), nullable=True),
        sa.Column("confidentiality_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["consultant_membership_id"], ["workspace_memberships.id"]),
        sa.ForeignKeyConstraint(["created_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["sponsor_membership_id"], ["workspace_memberships.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_programs_workspace_id"), "programs", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_programs_name"), "programs", ["name"], unique=False)
    op.create_index(
        op.f("ix_programs_sponsor_membership_id"),
        "programs",
        ["sponsor_membership_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_programs_consultant_membership_id"),
        "programs",
        ["consultant_membership_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_programs_created_by_subject_id"),
        "programs",
        ["created_by_subject_id"],
        unique=False,
    )

    op.create_table(
        "program_members",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("program_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_role", sa.String(length=64), nullable=False),
        sa.Column("created_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["membership_id"], ["workspace_memberships.id"]),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program_id", "membership_id", name="uq_program_member_program_membership"),
    )
    op.create_index(
        op.f("ix_program_members_workspace_id"),
        "program_members",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_program_members_program_id"),
        "program_members",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_program_members_membership_id"),
        "program_members",
        ["membership_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_program_members_created_by_subject_id"),
        "program_members",
        ["created_by_subject_id"],
        unique=False,
    )

    op.create_table(
        "use_cases",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("program_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("department", sa.String(length=200), nullable=True),
        sa.Column("owner_membership_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("recommendation", sa.String(length=120), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("priority_score", sa.Numeric(8, 3), nullable=True),
        sa.Column("score_version", sa.Integer(), nullable=True),
        sa.Column("confidence_level", sa.String(length=120), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_assessment_version", sa.Integer(), nullable=True),
        sa.Column("created_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["owner_membership_id"], ["workspace_memberships.id"]),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_use_cases_workspace_id"), "use_cases", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_use_cases_program_id"), "use_cases", ["program_id"], unique=False)
    op.create_index(op.f("ix_use_cases_title"), "use_cases", ["title"], unique=False)
    op.create_index(
        op.f("ix_use_cases_owner_membership_id"),
        "use_cases",
        ["owner_membership_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_use_cases_created_by_subject_id"),
        "use_cases",
        ["created_by_subject_id"],
        unique=False,
    )

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("ALTER TABLE programs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE program_members ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE use_cases ENABLE ROW LEVEL SECURITY")

    op.execute("ALTER TABLE programs FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE program_members FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE use_cases FORCE ROW LEVEL SECURITY")

    current_workspace = "nullif(current_setting('app.workspace_id', true), '')::uuid"
    scoped_tenant = (
        f"workspace_id = {current_workspace} "
        "AND current_setting('app.workspace_access_verified', true) = 'true'"
    )

    op.execute(
        "CREATE POLICY programs_workspace_scope ON programs "
        f"USING ({scoped_tenant}) WITH CHECK ({scoped_tenant})"
    )
    op.execute(
        "CREATE POLICY program_members_workspace_scope ON program_members "
        f"USING ({scoped_tenant}) WITH CHECK ({scoped_tenant})"
    )
    op.execute(
        "CREATE POLICY use_cases_workspace_scope ON use_cases "
        f"USING ({scoped_tenant}) WITH CHECK ({scoped_tenant})"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS use_cases_workspace_scope ON use_cases")
        op.execute("DROP POLICY IF EXISTS program_members_workspace_scope ON program_members")
        op.execute("DROP POLICY IF EXISTS programs_workspace_scope ON programs")
        op.execute("ALTER TABLE use_cases DISABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE program_members DISABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE programs DISABLE ROW LEVEL SECURITY")

    op.drop_index(op.f("ix_use_cases_created_by_subject_id"), table_name="use_cases")
    op.drop_index(op.f("ix_use_cases_owner_membership_id"), table_name="use_cases")
    op.drop_index(op.f("ix_use_cases_title"), table_name="use_cases")
    op.drop_index(op.f("ix_use_cases_program_id"), table_name="use_cases")
    op.drop_index(op.f("ix_use_cases_workspace_id"), table_name="use_cases")
    op.drop_table("use_cases")

    op.drop_index(op.f("ix_program_members_created_by_subject_id"), table_name="program_members")
    op.drop_index(op.f("ix_program_members_membership_id"), table_name="program_members")
    op.drop_index(op.f("ix_program_members_program_id"), table_name="program_members")
    op.drop_index(op.f("ix_program_members_workspace_id"), table_name="program_members")
    op.drop_table("program_members")

    op.drop_index(op.f("ix_programs_created_by_subject_id"), table_name="programs")
    op.drop_index(op.f("ix_programs_consultant_membership_id"), table_name="programs")
    op.drop_index(op.f("ix_programs_sponsor_membership_id"), table_name="programs")
    op.drop_index(op.f("ix_programs_name"), table_name="programs")
    op.drop_index(op.f("ix_programs_workspace_id"), table_name="programs")
    op.drop_table("programs")
