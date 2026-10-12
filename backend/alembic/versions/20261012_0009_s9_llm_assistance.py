"""Add S9 LLM assistance controls, rate limits, and circuit breaker state."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261012_0009"
down_revision = "20261012_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.add_column(
            sa.Column(
                "ai_assistance_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        batch_op.add_column(
            sa.Column("ai_assistance_consent_at", sa.DateTime(timezone=True), nullable=True),
        )
        batch_op.add_column(
            sa.Column("ai_assistance_consent_by_subject_id", sa.Uuid(), nullable=True),
        )
        batch_op.add_column(
            sa.Column(
                "ai_assistance_data_processing_note",
                sa.String(length=2000),
                nullable=True,
            ),
        )
        batch_op.create_index(
            op.f("ix_workspaces_ai_assistance_consent_by_subject_id"),
            ["ai_assistance_consent_by_subject_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_workspaces_ai_assistance_consent_by_subject_id",
            "identity_subjects",
            ["ai_assistance_consent_by_subject_id"],
            ["id"],
        )
        batch_op.alter_column("ai_assistance_enabled", server_default=None)

    op.create_table(
        "llm_rate_limit_buckets",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("actor_subject_id", sa.Uuid(), nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "actor_subject_id",
            "bucket_start",
            name="uq_llm_rate_limit_workspace_actor_bucket",
        ),
    )
    op.create_index(
        op.f("ix_llm_rate_limit_buckets_workspace_id"),
        "llm_rate_limit_buckets",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_rate_limit_buckets_actor_subject_id"),
        "llm_rate_limit_buckets",
        ["actor_subject_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_rate_limit_buckets_bucket_start"),
        "llm_rate_limit_buckets",
        ["bucket_start"],
        unique=False,
    )

    op.create_table(
        "llm_circuit_breakers",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("opened_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_code", sa.String(length=120), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "provider",
            name="uq_llm_circuit_workspace_provider",
        ),
    )
    op.create_index(
        op.f("ix_llm_circuit_breakers_workspace_id"),
        "llm_circuit_breakers",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_circuit_breakers_provider"),
        "llm_circuit_breakers",
        ["provider"],
        unique=False,
    )

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    current_workspace = "nullif(current_setting('app.workspace_id', true), '')::uuid"
    scoped_tenant = (
        f"workspace_id = {current_workspace} "
        "AND current_setting('app.workspace_access_verified', true) = 'true'"
    )
    for table_name in ("llm_rate_limit_buckets", "llm_circuit_breakers"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table_name}_workspace_scope ON {table_name} "
            f"USING ({scoped_tenant}) WITH CHECK ({scoped_tenant})"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in ("llm_circuit_breakers", "llm_rate_limit_buckets"):
            op.execute(f"DROP POLICY IF EXISTS {table_name}_workspace_scope ON {table_name}")
            op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")

    op.drop_index(op.f("ix_llm_circuit_breakers_provider"), table_name="llm_circuit_breakers")
    op.drop_index(op.f("ix_llm_circuit_breakers_workspace_id"), table_name="llm_circuit_breakers")
    op.drop_table("llm_circuit_breakers")

    op.drop_index(
        op.f("ix_llm_rate_limit_buckets_bucket_start"),
        table_name="llm_rate_limit_buckets",
    )
    op.drop_index(
        op.f("ix_llm_rate_limit_buckets_actor_subject_id"),
        table_name="llm_rate_limit_buckets",
    )
    op.drop_index(
        op.f("ix_llm_rate_limit_buckets_workspace_id"),
        table_name="llm_rate_limit_buckets",
    )
    op.drop_table("llm_rate_limit_buckets")

    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.drop_constraint(
            "fk_workspaces_ai_assistance_consent_by_subject_id",
            type_="foreignkey",
        )
        batch_op.drop_index(op.f("ix_workspaces_ai_assistance_consent_by_subject_id"))
        batch_op.drop_column("ai_assistance_data_processing_note")
        batch_op.drop_column("ai_assistance_consent_by_subject_id")
        batch_op.drop_column("ai_assistance_consent_at")
        batch_op.drop_column("ai_assistance_enabled")
