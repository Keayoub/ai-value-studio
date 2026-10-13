"""Enable PostgreSQL RLS for tenant tables."""

from __future__ import annotations

from alembic import op


revision = "20261011_0002"
down_revision = "20261011_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workspace_memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")

    op.execute("ALTER TABLE workspaces FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workspace_memberships FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY")

    current_workspace = "nullif(current_setting('app.workspace_id', true), '')::uuid"
    scoped_workspace = (
        f"id = {current_workspace} "
        "AND current_setting('app.workspace_access_verified', true) = 'true'"
    )
    scoped_tenant = (
        f"workspace_id = {current_workspace} "
        "AND current_setting('app.workspace_access_verified', true) = 'true'"
    )
    create_workspace = (
        f"id = {current_workspace} "
        "AND current_setting('app.workspace_create_allowed', true) = 'true'"
    )
    actor_membership = (
        "identity_subject_id = nullif(current_setting('app.identity_subject_id', true), '')::uuid "
        "AND status = 'ACTIVE'"
    )
    actor_workspace = (
        "EXISTS ("
        " SELECT 1"
        " FROM workspace_memberships"
        " WHERE workspace_memberships.workspace_id = workspaces.id"
        "   AND workspace_memberships.identity_subject_id ="
        " nullif(current_setting('app.identity_subject_id', true), '')::uuid"
        "   AND workspace_memberships.status = 'ACTIVE'"
        ")"
    )

    op.execute(
        "CREATE POLICY workspaces_actor_discovery ON workspaces "
        f"FOR SELECT USING ({actor_workspace})"
    )
    op.execute(
        "CREATE POLICY workspaces_workspace_scope_select ON workspaces "
        f"FOR SELECT USING ({scoped_workspace})"
    )
    op.execute(
        "CREATE POLICY workspaces_workspace_scope_modify ON workspaces "
        f"FOR UPDATE USING ({scoped_workspace}) WITH CHECK ({scoped_workspace})"
    )
    op.execute(
        "CREATE POLICY workspaces_workspace_create ON workspaces "
        f"FOR INSERT WITH CHECK ({create_workspace})"
    )
    op.execute(
        "CREATE POLICY workspace_memberships_actor_discovery ON workspace_memberships "
        f"FOR SELECT USING ({actor_membership})"
    )
    op.execute(
        "CREATE POLICY workspace_memberships_workspace_scope ON workspace_memberships "
        f"USING ({scoped_tenant}) WITH CHECK ({scoped_tenant})"
    )
    op.execute(
        "CREATE POLICY audit_events_workspace_scope ON audit_events "
        f"USING ({scoped_tenant}) WITH CHECK ({scoped_tenant})"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP POLICY IF EXISTS audit_events_workspace_scope ON audit_events")
    op.execute(
        "DROP POLICY IF EXISTS workspace_memberships_workspace_scope ON workspace_memberships"
    )
    op.execute(
        "DROP POLICY IF EXISTS workspace_memberships_actor_discovery ON workspace_memberships"
    )
    op.execute("DROP POLICY IF EXISTS workspaces_workspace_create ON workspaces")
    op.execute("DROP POLICY IF EXISTS workspaces_workspace_scope_modify ON workspaces")
    op.execute("DROP POLICY IF EXISTS workspaces_workspace_scope_select ON workspaces")
    op.execute("DROP POLICY IF EXISTS workspaces_actor_discovery ON workspaces")

    op.execute("ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workspace_memberships DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workspaces DISABLE ROW LEVEL SECURITY")
