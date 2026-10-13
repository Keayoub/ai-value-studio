"""Initial identity/workspace schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261011_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_subjects",
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("issuer", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("oid", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issuer", "tenant_id", "oid", name="uq_identity_subject_issuer_tid_oid"),
        sa.UniqueConstraint("subject"),
    )
    op.create_index(op.f("ix_identity_subjects_subject"), "identity_subjects", ["subject"], unique=False)
    op.create_index(op.f("ix_identity_subjects_issuer"), "identity_subjects", ["issuer"], unique=False)
    op.create_index(op.f("ix_identity_subjects_tenant_id"), "identity_subjects", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_identity_subjects_oid"), "identity_subjects", ["oid"], unique=False)

    op.create_table(
        "workspaces",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sector", sa.String(length=120), nullable=True),
        sa.Column("country_region", sa.String(length=120), nullable=True),
        sa.Column("size_band", sa.String(length=32), nullable=True),
        sa.Column("default_language", sa.String(length=16), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("branding_json", sa.JSON(), nullable=True),
        sa.Column("confidentiality_policy", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_subject_id"], ["identity_subjects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workspaces_created_by_subject_id"), "workspaces", ["created_by_subject_id"], unique=False)
    op.create_index(op.f("ix_workspaces_name"), "workspaces", ["name"], unique=False)

    op.create_table(
        "workspace_memberships",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("identity_subject_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_subject_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["identity_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "identity_subject_id",
            name="uq_workspace_membership_workspace_subject",
        ),
    )
    op.create_index(
        op.f("ix_workspace_memberships_workspace_id"),
        "workspace_memberships",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workspace_memberships_identity_subject_id"),
        "workspace_memberships",
        ["identity_subject_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workspace_memberships_created_by_subject_id"),
        "workspace_memberships",
        ["created_by_subject_id"],
        unique=False,
    )

    op.create_table(
        "audit_events",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("actor_subject_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=200), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=False),
        sa.Column("request_id", sa.String(length=120), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("before_hash", sa.String(length=64), nullable=True),
        sa.Column("after_hash", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["actor_subject_id"], ["identity_subjects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_workspace_id"), "audit_events", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_audit_events_actor_subject_id"), "audit_events", ["actor_subject_id"], unique=False)
    op.create_index(op.f("ix_audit_events_request_id"), "audit_events", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_events_request_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_actor_subject_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_workspace_id"), table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index(op.f("ix_workspace_memberships_created_by_subject_id"), table_name="workspace_memberships")
    op.drop_index(op.f("ix_workspace_memberships_identity_subject_id"), table_name="workspace_memberships")
    op.drop_index(op.f("ix_workspace_memberships_workspace_id"), table_name="workspace_memberships")
    op.drop_table("workspace_memberships")

    op.drop_index(op.f("ix_workspaces_name"), table_name="workspaces")
    op.drop_index(op.f("ix_workspaces_created_by_subject_id"), table_name="workspaces")
    op.drop_table("workspaces")

    op.drop_index(op.f("ix_identity_subjects_oid"), table_name="identity_subjects")
    op.drop_index(op.f("ix_identity_subjects_tenant_id"), table_name="identity_subjects")
    op.drop_index(op.f("ix_identity_subjects_issuer"), table_name="identity_subjects")
    op.drop_index(op.f("ix_identity_subjects_subject"), table_name="identity_subjects")
    op.drop_table("identity_subjects")
