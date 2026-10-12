"""Add S8 versioned documents and immutable storage metadata."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261012_0008"
down_revision = "20261012_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("use_case_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_version_no", sa.Integer(), nullable=True),
        sa.Column("created_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["use_case_id"], ["use_cases.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "use_case_id",
            "type",
            "language",
            name="uq_document_use_case_type_language",
        ),
    )
    op.create_index(op.f("ix_documents_workspace_id"), "documents", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_documents_use_case_id"), "documents", ["use_case_id"], unique=False)
    op.create_index(
        op.f("ix_documents_created_by_subject_id"),
        "documents",
        ["created_by_subject_id"],
        unique=False,
    )

    op.create_table(
        "document_versions",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("source_assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_assessment_version_no", sa.Integer(), nullable=False),
        sa.Column("source_scorecard_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_scorecard_version_no", sa.Integer(), nullable=False),
        sa.Column("source_review_id", sa.Uuid(), nullable=False),
        sa.Column("source_review_status", sa.String(length=32), nullable=False),
        sa.Column("source_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("ai_assisted_sections_json", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("response_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("approved_by_subject_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["created_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["source_assessment_version_id"], ["assessment_versions.id"]),
        sa.ForeignKeyConstraint(["source_review_id"], ["reviews.id"]),
        sa.ForeignKeyConstraint(["source_scorecard_version_id"], ["scorecard_versions.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "version_no",
            "format",
            name="uq_document_version_document_version_format",
        ),
        sa.UniqueConstraint(
            "created_by_subject_id",
            "idempotency_key",
            name="uq_document_version_actor_idempotency_key",
        ),
    )
    op.create_index(
        op.f("ix_document_versions_workspace_id"),
        "document_versions",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_versions_document_id"),
        "document_versions",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_versions_source_assessment_version_id"),
        "document_versions",
        ["source_assessment_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_versions_source_scorecard_version_id"),
        "document_versions",
        ["source_scorecard_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_versions_source_review_id"),
        "document_versions",
        ["source_review_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_versions_approved_by_subject_id"),
        "document_versions",
        ["approved_by_subject_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_versions_created_by_subject_id"),
        "document_versions",
        ["created_by_subject_id"],
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
    for table_name in ("documents", "document_versions"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table_name}_workspace_scope ON {table_name} "
            f"USING ({scoped_tenant}) WITH CHECK ({scoped_tenant})"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in ("document_versions", "documents"):
            op.execute(f"DROP POLICY IF EXISTS {table_name}_workspace_scope ON {table_name}")
            op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")

    op.drop_index(
        op.f("ix_document_versions_created_by_subject_id"),
        table_name="document_versions",
    )
    op.drop_index(
        op.f("ix_document_versions_approved_by_subject_id"),
        table_name="document_versions",
    )
    op.drop_index(
        op.f("ix_document_versions_source_review_id"),
        table_name="document_versions",
    )
    op.drop_index(
        op.f("ix_document_versions_source_scorecard_version_id"),
        table_name="document_versions",
    )
    op.drop_index(
        op.f("ix_document_versions_source_assessment_version_id"),
        table_name="document_versions",
    )
    op.drop_index(op.f("ix_document_versions_document_id"), table_name="document_versions")
    op.drop_index(op.f("ix_document_versions_workspace_id"), table_name="document_versions")
    op.drop_table("document_versions")

    op.drop_index(op.f("ix_documents_created_by_subject_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_use_case_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_workspace_id"), table_name="documents")
    op.drop_table("documents")

