"""Bind business RLS to active actors and protect nested tenant references."""

from __future__ import annotations

from alembic import op

revision = "20261012_0010"
down_revision = "20261012_0009"
branch_labels = None
depends_on = None

WORKSPACE_TABLES = (
    "audit_events",
    "programs",
    "program_members",
    "use_cases",
    "assessment_versions",
    "answers",
    "hypotheses",
    "value_assessments",
    "score_configuration_versions",
    "scorecard_versions",
    "dimension_scores",
    "reviews",
    "review_comments",
    "approvals",
    "documents",
    "document_versions",
    "llm_rate_limit_buckets",
    "llm_circuit_breakers",
)

# Each entry is (child column, parent table, whether a global template is allowed).
PARENTS = {
    "programs": (("sponsor_membership_id", "workspace_memberships", False),
                 ("consultant_membership_id", "workspace_memberships", False),
                 ("questionnaire_template_version_id", "questionnaire_template_versions", True)),
    "program_members": (("program_id", "programs", False),
                        ("membership_id", "workspace_memberships", False)),
    "use_cases": (("program_id", "programs", False),
                  ("owner_membership_id", "workspace_memberships", False)),
    "assessment_versions": (("use_case_id", "use_cases", False),
                            ("template_version_id", "questionnaire_template_versions", True),
                            ("respondent_membership_id", "workspace_memberships", False)),
    "answers": (("assessment_version_id", "assessment_versions", False),
                ("captured_for_membership_id", "workspace_memberships", False)),
    "hypotheses": (("use_case_id", "use_cases", False),
                   ("assessment_version_id", "assessment_versions", False)),
    "value_assessments": (("use_case_id", "use_cases", False),
                          ("assessment_version_id", "assessment_versions", False)),
    "scorecard_versions": (("use_case_id", "use_cases", False),
                           ("assessment_version_id", "assessment_versions", False),
                           ("value_assessment_id", "value_assessments", False),
                           ("score_configuration_version_id", "score_configuration_versions", False)),
    "dimension_scores": (("scorecard_version_id", "scorecard_versions", False),),
    "reviews": (("use_case_id", "use_cases", False),
                ("assessment_version_id", "assessment_versions", False)),
    "review_comments": (("use_case_id", "use_cases", False),
                        ("review_id", "reviews", False),
                        ("parent_comment_id", "review_comments", False)),
    "approvals": (("use_case_id", "use_cases", False),
                  ("review_id", "reviews", False)),
    "documents": (("use_case_id", "use_cases", False),),
    "document_versions": (("document_id", "documents", False),
                          ("source_assessment_version_id", "assessment_versions", False),
                          ("source_scorecard_version_id", "scorecard_versions", False),
                          ("source_review_id", "reviews", False)),
}


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    # The migration owner must BYPASSRLS; the application role must not.
    op.execute("""
        CREATE FUNCTION app_actor_has_workspace(target uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        SET row_security = off
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM public.workspace_memberships
                WHERE workspace_id = target
                  AND identity_subject_id =
                      nullif(current_setting('app.identity_subject_id', true), '')::uuid
                  AND status = 'ACTIVE'
            )
        $$
    """)
    scoped = (
        "current_setting('app.workspace_access_verified', true) = 'true' "
        "AND app_actor_has_workspace(workspace_id)"
    )
    for table in ("workspace_memberships", *WORKSPACE_TABLES):
        op.execute(
            f"CREATE POLICY {table}_actor_guard ON {table} AS RESTRICTIVE "
            f"USING ({scoped}) WITH CHECK ({scoped})"
        )
    op.execute("DROP POLICY workspaces_actor_discovery ON workspaces")
    op.execute("""
        CREATE POLICY workspaces_actor_discovery ON workspaces FOR SELECT
        USING (EXISTS (
            SELECT 1 FROM workspace_memberships m
            WHERE m.workspace_id = workspaces.id
              AND m.identity_subject_id =
                  nullif(current_setting('app.identity_subject_id', true), '')::uuid
              AND m.status = 'ACTIVE'
        ))
    """)
    op.execute("DROP POLICY workspace_memberships_actor_discovery ON workspace_memberships")
    op.execute(
        "CREATE POLICY workspace_memberships_actor_discovery ON workspace_memberships "
        "FOR SELECT USING (identity_subject_id = "
        "nullif(current_setting('app.identity_subject_id', true), '')::uuid AND status = 'ACTIVE')"
    )
    # Restrictive policies also apply to discovery SELECTs.
    op.execute("DROP POLICY workspace_memberships_actor_guard ON workspace_memberships")
    op.execute(
        "CREATE POLICY workspace_memberships_actor_guard ON workspace_memberships "
        "AS RESTRICTIVE USING ("
        "identity_subject_id = nullif(current_setting('app.identity_subject_id', true), '')::uuid "
        "AND status = 'ACTIVE' OR (" + scoped + ")) "
        "WITH CHECK ((" + scoped + ") OR ("
        "current_setting('app.workspace_create_allowed', true) = 'true' "
        "AND workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid "
        "AND identity_subject_id = nullif(current_setting('app.identity_subject_id', true), '')::uuid "
        "AND created_by_subject_id = identity_subject_id AND status = 'ACTIVE'))"
    )
    op.execute(
        "CREATE POLICY workspaces_actor_guard ON workspaces AS RESTRICTIVE "
        "USING (app_actor_has_workspace(id)) "
        "WITH CHECK (app_actor_has_workspace(id) OR ("
        "current_setting('app.workspace_create_allowed', true) = 'true' "
        "AND id = nullif(current_setting('app.workspace_id', true), '')::uuid "
        "AND created_by_subject_id = "
        "nullif(current_setting('app.identity_subject_id', true), '')::uuid))"
    )
    op.execute(
        "CREATE POLICY questionnaire_template_versions_actor_guard "
        "ON questionnaire_template_versions AS RESTRICTIVE "
        "USING ((" + scoped + ") OR (workspace_id IS NULL "
        "AND current_setting('app.workspace_access_verified', true) = 'true' "
        "AND app_actor_has_workspace("
        "nullif(current_setting('app.workspace_id', true), '')::uuid))) "
        "WITH CHECK (workspace_id IS NOT NULL AND " + scoped + ")"
    )
    op.execute("ALTER TABLE question_definitions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE question_definitions FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY question_definitions_read ON question_definitions
        FOR SELECT USING (EXISTS (
            SELECT 1 FROM questionnaire_template_versions t
            WHERE t.id = template_version_id
        ))
    """)
    op.execute("""
        CREATE POLICY question_definitions_write ON question_definitions
        USING (EXISTS (
            SELECT 1 FROM questionnaire_template_versions t
            WHERE t.id = template_version_id AND t.workspace_id IS NOT NULL
        ))
        WITH CHECK (EXISTS (
            SELECT 1 FROM questionnaire_template_versions t
            WHERE t.id = template_version_id AND t.workspace_id IS NOT NULL
        ))
    """)
    # Parent integrity must check stored rows, even when their RLS hides them from the caller.
    op.execute("""
        CREATE FUNCTION app_check_tenant_parent() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        SET row_security = off AS $$
        DECLARE
            parent_id uuid;
            matches_parent boolean;
            i integer;
        BEGIN
            FOR i IN 0..(TG_NARGS / 3 - 1) LOOP
                EXECUTE format('SELECT ($1).%I', TG_ARGV[i * 3])
                    INTO parent_id USING NEW;
                IF parent_id IS NOT NULL THEN
                    EXECUTE format(
                        'SELECT EXISTS (SELECT 1 FROM public.%I WHERE id = $1 AND '
                        || '(workspace_id = $2 OR ($3 AND workspace_id IS NULL)))',
                        TG_ARGV[i * 3 + 1]
                    ) INTO matches_parent
                      USING parent_id, NEW.workspace_id, TG_ARGV[i * 3 + 2]::boolean;
                    IF NOT matches_parent THEN
                        RAISE EXCEPTION 'Tenant parent mismatch: %.%', TG_TABLE_NAME,
                            TG_ARGV[i * 3] USING ERRCODE = '23503';
                    END IF;
                END IF;
            END LOOP;
            RETURN NEW;
        END $$
    """)
    for table, parents in PARENTS.items():
        args = ", ".join(f"'{column}', '{parent}', '{str(global_ok).lower()}'"
                         for column, parent, global_ok in parents)
        op.execute(
            f"CREATE TRIGGER {table}_tenant_parents BEFORE INSERT OR UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION app_check_tenant_parent({args})"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in reversed(tuple(PARENTS)):
        op.execute(f"DROP TRIGGER {table}_tenant_parents ON {table}")
    op.execute("DROP FUNCTION app_check_tenant_parent()")
    op.execute("DROP POLICY question_definitions_write ON question_definitions")
    op.execute("DROP POLICY question_definitions_read ON question_definitions")
    op.execute("ALTER TABLE question_definitions DISABLE ROW LEVEL SECURITY")
    for table in ("questionnaire_template_versions", "workspaces",
                  "workspace_memberships", *WORKSPACE_TABLES):
        op.execute(f"DROP POLICY {table}_actor_guard ON {table}")
    op.execute("DROP POLICY workspaces_actor_discovery ON workspaces")
    op.execute(
        "CREATE POLICY workspaces_actor_discovery ON workspaces FOR SELECT "
        "USING (EXISTS (SELECT 1 FROM workspace_memberships m "
        "WHERE m.workspace_id = workspaces.id AND m.identity_subject_id = "
        "nullif(current_setting('app.identity_subject_id', true), '')::uuid "
        "AND m.status = 'ACTIVE'))"
    )
    op.execute("DROP POLICY workspace_memberships_actor_discovery ON workspace_memberships")
    op.execute(
        "CREATE POLICY workspace_memberships_actor_discovery ON workspace_memberships "
        "FOR SELECT USING (identity_subject_id = "
        "nullif(current_setting('app.identity_subject_id', true), '')::uuid "
        "AND status = 'ACTIVE')"
    )
    op.execute("DROP FUNCTION app_actor_has_workspace(uuid)")
