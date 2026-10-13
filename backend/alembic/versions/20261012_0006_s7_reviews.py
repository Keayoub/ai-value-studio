"""Add S7 review, comment, and approval workflow tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261012_0006"
down_revision = "20261012_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("assessment_versions") as batch_op:
        batch_op.add_column(
            sa.Column("approved_by_subject_id", sa.Uuid(), nullable=True),
        )
        batch_op.add_column(
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_assessment_versions_approved_by_subject_id",
            "identity_subjects",
            ["approved_by_subject_id"],
            ["id"],
        )
        batch_op.create_index(
            op.f("ix_assessment_versions_approved_by_subject_id"),
            ["approved_by_subject_id"],
            unique=False,
        )

    op.create_table(
        "reviews",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("use_case_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("recommendation", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.String(length=4000), nullable=False),
        sa.Column("risks_json", sa.JSON(), nullable=False),
        sa.Column("submitted_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by_subject_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.String(length=4000), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assessment_version_id"], ["assessment_versions.id"]),
        sa.ForeignKeyConstraint(["decided_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["submitted_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["use_case_id"], ["use_cases.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_version_id", name="uq_review_assessment_version"),
    )
    op.create_index(op.f("ix_reviews_workspace_id"), "reviews", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_reviews_use_case_id"), "reviews", ["use_case_id"], unique=False)
    op.create_index(
        op.f("ix_reviews_assessment_version_id"),
        "reviews",
        ["assessment_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reviews_submitted_by_subject_id"),
        "reviews",
        ["submitted_by_subject_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reviews_decided_by_subject_id"),
        "reviews",
        ["decided_by_subject_id"],
        unique=False,
    )

    op.create_table(
        "review_comments",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("use_case_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("parent_comment_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.String(length=4000), nullable=False),
        sa.Column("author_subject_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["parent_comment_id"], ["review_comments.id"]),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"]),
        sa.ForeignKeyConstraint(["use_case_id"], ["use_cases.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_review_comments_workspace_id"),
        "review_comments",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_comments_use_case_id"),
        "review_comments",
        ["use_case_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_comments_review_id"),
        "review_comments",
        ["review_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_comments_parent_comment_id"),
        "review_comments",
        ["parent_comment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_comments_author_subject_id"),
        "review_comments",
        ["author_subject_id"],
        unique=False,
    )

    op.create_table(
        "approvals",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("use_case_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("decision_reason", sa.String(length=4000), nullable=False),
        sa.Column("approver_subject_id", sa.Uuid(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approver_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"]),
        sa.ForeignKeyConstraint(["use_case_id"], ["use_cases.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id", name="uq_approval_review"),
    )
    op.create_index(op.f("ix_approvals_workspace_id"), "approvals", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_approvals_use_case_id"), "approvals", ["use_case_id"], unique=False)
    op.create_index(op.f("ix_approvals_review_id"), "approvals", ["review_id"], unique=False)
    op.create_index(
        op.f("ix_approvals_approver_subject_id"),
        "approvals",
        ["approver_subject_id"],
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
    for table_name in ("reviews", "review_comments", "approvals"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table_name}_workspace_scope ON {table_name} "
            f"USING ({scoped_tenant}) WITH CHECK ({scoped_tenant})"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in ("approvals", "review_comments", "reviews"):
            op.execute(f"DROP POLICY IF EXISTS {table_name}_workspace_scope ON {table_name}")
            op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")

    op.drop_index(op.f("ix_approvals_approver_subject_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_review_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_use_case_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_workspace_id"), table_name="approvals")
    op.drop_table("approvals")

    op.drop_index(
        op.f("ix_review_comments_author_subject_id"),
        table_name="review_comments",
    )
    op.drop_index(
        op.f("ix_review_comments_parent_comment_id"),
        table_name="review_comments",
    )
    op.drop_index(op.f("ix_review_comments_review_id"), table_name="review_comments")
    op.drop_index(op.f("ix_review_comments_use_case_id"), table_name="review_comments")
    op.drop_index(op.f("ix_review_comments_workspace_id"), table_name="review_comments")
    op.drop_table("review_comments")

    op.drop_index(op.f("ix_reviews_decided_by_subject_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_submitted_by_subject_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_assessment_version_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_use_case_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_workspace_id"), table_name="reviews")
    op.drop_table("reviews")

    with op.batch_alter_table("assessment_versions") as batch_op:
        batch_op.drop_index(op.f("ix_assessment_versions_approved_by_subject_id"))
        batch_op.drop_constraint(
            "fk_assessment_versions_approved_by_subject_id",
            type_="foreignkey",
        )
        batch_op.drop_column("approved_at")
        batch_op.drop_column("approved_by_subject_id")
