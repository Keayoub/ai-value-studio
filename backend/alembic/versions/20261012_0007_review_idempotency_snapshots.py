"""Add approval idempotency response snapshots."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261012_0007"
down_revision = "20261012_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("approvals") as batch_op:
        batch_op.add_column(sa.Column("response_snapshot_json", sa.JSON(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_approval_approver_idempotency_key",
            ["approver_subject_id", "idempotency_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("approvals") as batch_op:
        batch_op.drop_constraint("uq_approval_approver_idempotency_key", type_="unique")
        batch_op.drop_column("response_snapshot_json")
