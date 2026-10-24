from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import MetaData, create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.sql.sqltypes import JSON, Boolean, Date, DateTime, Numeric, String, Uuid

BUSINESS_TABLES = (
    "workspaces", "workspace_memberships", "audit_events",
    "programs", "program_members", "use_cases",
    "questionnaire_template_versions", "question_definitions",
    "assessment_versions", "answers", "hypotheses",
    "value_assessments", "score_configuration_versions", "scorecard_versions",
    "dimension_scores", "reviews", "review_comments", "approvals",
    "documents", "document_versions", "llm_rate_limit_buckets", "llm_circuit_breakers",
)

ORDER = (
    "questionnaire_template_versions", "programs", "program_members", "use_cases",
    "assessment_versions", "answers", "hypotheses", "value_assessments",
    "score_configuration_versions", "scorecard_versions", "dimension_scores",
    "reviews", "review_comments", "approvals", "documents", "document_versions",
    "audit_events", "llm_rate_limit_buckets", "llm_circuit_breakers",
)


def _seed_row(table, workspace_id, actor_id, parent_ids, global_template_id):
    row = {}
    for column in table.columns:
        name = column.name
        if name == "workspace_id":
            value = workspace_id
        elif name.endswith("_subject_id"):
            value = actor_id
        elif name in {"template_version_id", "questionnaire_template_version_id"}:
            value = global_template_id
        elif column.foreign_keys and not column.nullable:
            parent = next(iter(column.foreign_keys)).column.table.name
            value = parent_ids[parent]
        elif column.nullable:
            continue
        elif name == "id" or isinstance(column.type, Uuid):
            value = uuid.uuid4()
        elif isinstance(column.type, DateTime):
            value = datetime.now(UTC)
        elif isinstance(column.type, Date):
            value = date.today()
        elif isinstance(column.type, JSON):
            value = {}
        elif isinstance(column.type, Boolean):
            value = True
        elif isinstance(column.type, Numeric):
            value = 1
        elif isinstance(column.type, String):
            value = uuid.uuid4().hex[:column.type.length or 32]
        elif column.type.python_type is int:
            value = 1
        else:
            raise AssertionError(f"No seed value for {table.name}.{name}: {column.type}")
        row[name] = value
    return row


def _insert_probe_values(table_name, row, other_actor_id, alternate_ids):
    values = dict(row)
    values["id"] = uuid.uuid4()
    if table_name == "workspace_memberships":
        values["identity_subject_id"] = other_actor_id
    elif table_name == "program_members":
        values["program_id"] = alternate_ids["programs"]
    elif table_name == "reviews":
        values["assessment_version_id"] = alternate_ids["assessment_versions"]
    elif table_name == "approvals":
        values["review_id"] = alternate_ids["reviews"]
    elif table_name == "llm_rate_limit_buckets":
        values["bucket_start"] += timedelta(seconds=1)
    else:
        distinct_keys = {
            "questionnaire_template_versions": "template_key",
            "question_definitions": "question_key",
            "assessment_versions": "version",
            "answers": "question_key",
            "value_assessments": "revision",
            "score_configuration_versions": "version",
            "scorecard_versions": "version",
            "dimension_scores": "dimension",
            "documents": "type",
            "document_versions": "version_no",
            "llm_circuit_breakers": "provider",
        }
        key = distinct_keys.get(table_name)
        if key is not None:
            values[key] = uuid.uuid4().hex if isinstance(values[key], str) else 2
    if table_name == "document_versions":
        values["idempotency_key"] = uuid.uuid4().hex
    return values


def test_business_rls_inventory_and_cross_tenant_dml(postgres_test_urls) -> None:
    admin = create_engine(postgres_test_urls["admin_url"])
    app = create_engine(postgres_test_urls["app_url"])
    metadata = MetaData()
    metadata.reflect(bind=admin)
    assert set(metadata.tables) == set(BUSINESS_TABLES) | {
        "identity_subjects", "alembic_version"
    }

    with admin.connect() as connection:
        inventory = connection.execute(text("""
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                   count(p.policyname) AS policies
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_policies p ON p.schemaname = n.nspname AND p.tablename = c.relname
            WHERE n.nspname = 'public' AND c.relname = ANY(:tables)
            GROUP BY c.relname, c.relrowsecurity, c.relforcerowsecurity
        """), {"tables": list(BUSINESS_TABLES)}).all()
        role = connection.execute(text(
            "SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = :role"
        ), {"role": postgres_test_urls["role_name"]}).one()
    assert len(inventory) == len(BUSINESS_TABLES)
    assert all(
        enabled and forced and policies > 0 for _, enabled, forced, policies in inventory
    )
    assert not role.rolbypassrls and not role.rolsuper

    actors = [uuid.uuid4(), uuid.uuid4()]
    workspaces = [uuid.uuid4(), uuid.uuid4()]
    ids = []
    seeded_rows = []
    alternate_ids = []
    with admin.begin() as connection:
        for index in range(2):
            actor_id, workspace_id = actors[index], workspaces[index]
            connection.execute(metadata.tables["identity_subjects"].insert().values(
                id=actor_id, subject=f"dev:rls-{index}", issuer="dev", tenant_id="dev",
                oid=f"rls-{index}", created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
            ))
            connection.execute(metadata.tables["workspaces"].insert().values(
                id=workspace_id, name=f"Tenant {index}", default_language="en",
                confidentiality_policy="internal", status="active",
                ai_assistance_enabled=False,
                created_by_subject_id=actor_id,
                created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
            ))
            connection.execute(metadata.tables["workspace_memberships"].insert().values(
                id=uuid.uuid4(), workspace_id=workspace_id, identity_subject_id=actor_id,
                role="WorkspaceAdmin", status="ACTIVE", created_by_subject_id=actor_id,
                created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
            ))
            global_template_id = connection.execute(select(
                metadata.tables["questionnaire_template_versions"].c.id
            ).where(
                metadata.tables["questionnaire_template_versions"].c.workspace_id.is_(None)
            )).scalar_one()
            parent_ids = {}
            rows = {"workspaces": workspace_id}
            membership_id = connection.execute(select(
                metadata.tables["workspace_memberships"].c.id
            ).where(
                metadata.tables["workspace_memberships"].c.workspace_id == workspace_id
            )).scalar_one()
            rows["workspace_memberships"] = membership_id
            parent_ids["workspace_memberships"] = membership_id
            for table_name in ORDER:
                table = metadata.tables[table_name]
                row = _seed_row(table, workspace_id, actor_id, parent_ids, global_template_id)
                connection.execute(table.insert().values(**row))
                rows[table_name] = row["id"]
                parent_ids[table_name] = row["id"]
            alternates = {}
            for table_name in ("programs", "assessment_versions", "reviews"):
                table = metadata.tables[table_name]
                row = _seed_row(table, workspace_id, actor_id, parent_ids, global_template_id)
                if table_name == "assessment_versions":
                    row["version"] = 2
                elif table_name == "reviews":
                    row["assessment_version_id"] = alternates["assessment_versions"]
                connection.execute(table.insert().values(**row))
                alternates[table_name] = row["id"]
            alternate_ids.append(alternates)
            template = metadata.tables["questionnaire_template_versions"]
            template_row = _seed_row(
                template, workspace_id, actor_id, parent_ids, global_template_id
            )
            connection.execute(template.insert().values(**template_row))
            rows["questionnaire_template_versions"] = template_row["id"]
            questions = metadata.tables["question_definitions"]
            question_row = _seed_row(
                questions, workspace_id, actor_id, parent_ids, global_template_id
            )
            question_row["template_version_id"] = template_row["id"]
            connection.execute(questions.insert().values(**question_row))
            rows["question_definitions"] = question_row["id"]
            ids.append(rows)
            seeded_rows.append({
                table_name: dict(connection.execute(
                    select(metadata.tables[table_name]).where(
                        metadata.tables[table_name].c.id == row_id
                    )
                ).mappings().one())
                for table_name, row_id in rows.items()
            })

    try:
        for actor_index, workspace_index, verified in (
            (None, None, False), (None, 0, True), (0, 0, False), (0, 1, True),
            (1, 0, True), (0, 0, True),
        ):
            authorized = actor_index == workspace_index and verified
            with app.begin() as connection:
                if actor_index is not None:
                    connection.execute(text(
                        "SELECT set_config('app.identity_subject_id', :actor, true)"
                    ), {"actor": str(actors[actor_index])})
                if workspace_index is not None:
                    connection.execute(text(
                        "SELECT set_config('app.workspace_id', :workspace, true)"
                    ), {"workspace": str(workspaces[workspace_index])})
                if verified:
                    connection.execute(text(
                        "SELECT set_config('app.workspace_access_verified', 'true', true)"
                    ))
                for global_table in (
                    "questionnaire_template_versions", "question_definitions"
                ):
                    table = metadata.tables[global_table]
                    foreign_key = (
                        table.c.workspace_id.is_(None)
                        if global_table == "questionnaire_template_versions"
                        else table.c.template_version_id == global_template_id
                    )
                    assert (connection.execute(
                        select(table.c.id).where(foreign_key).limit(1)
                    ).scalar_one_or_none() is not None) == authorized
                for table_name in BUSINESS_TABLES:
                    table = metadata.tables[table_name]
                    target = ids[workspace_index if workspace_index is not None else 0][table_name]
                    # Actor discovery is intentionally available before verification.
                    discovery = table_name in {"workspaces", "workspace_memberships"}
                    visible = connection.execute(
                        select(table.c.id).where(table.c.id == target)
                    ).scalar_one_or_none()
                    assert (visible is not None) == (
                        authorized or (
                            discovery and actor_index is not None
                            and actor_index == workspace_index
                        )
                    ), (table_name, actor_index, workspace_index, verified)
                    if not authorized:
                        assert connection.execute(
                            table.update().where(table.c.id == target).values(
                                id=uuid.uuid4()
                            )
                        ).rowcount == 0
                        assert connection.execute(
                            table.delete().where(table.c.id == target)
                        ).rowcount == 0
                        for source in (0, 1):
                            values = _insert_probe_values(
                                table_name, seeded_rows[source][table_name],
                                actors[1 - source], alternate_ids[source]
                            )
                            with pytest.raises(DBAPIError) as error, connection.begin_nested():
                                connection.execute(table.insert().values(**values))
                            assert error.value.orig.sqlstate == "42501", (
                                table_name, source, error.value.orig.sqlstate
                            )

        with app.begin() as connection:
            for key, value in (
                ("app.identity_subject_id", actors[0]),
                ("app.workspace_id", workspaces[0]),
                ("app.workspace_access_verified", "true"),
            ):
                connection.execute(text(
                    "SELECT set_config(:key, :value, true)"
                ), {"key": key, "value": str(value)})
            for table_name in BUSINESS_TABLES:
                table = metadata.tables[table_name]
                if table_name == "question_definitions":
                    # A global question is readable, but its definition is not writable.
                    global_id = connection.execute(
                        select(table.c.id).where(
                            table.c.template_version_id == global_template_id
                        ).limit(1)
                    ).scalar_one()
                    assert global_id
                    with pytest.raises(DBAPIError) as error, connection.begin_nested():
                        values = _insert_probe_values(
                            table_name, seeded_rows[0][table_name],
                            actors[1], alternate_ids[0]
                        )
                        values["template_version_id"] = global_template_id
                        connection.execute(table.insert().values(**values))
                    assert error.value.orig.sqlstate == "42501", error.value.orig.sqlstate
                    with pytest.raises(DBAPIError) as error, connection.begin_nested():
                        values["id"] = uuid.uuid4()
                        values["template_version_id"] = ids[1][
                            "questionnaire_template_versions"
                        ]
                        connection.execute(table.insert().values(**values))
                    assert error.value.orig.sqlstate == "42501", error.value.orig.sqlstate
                    with pytest.raises(DBAPIError) as error, connection.begin_nested():
                        connection.execute(table.update().where(
                            table.c.id == ids[0]["question_definitions"]
                        ).values(
                            template_version_id=ids[1][
                                "questionnaire_template_versions"
                            ]
                        ))
                    assert error.value.orig.sqlstate == "42501", error.value.orig.sqlstate
                    assert connection.execute(table.delete().where(
                        table.c.id == global_id
                    )).rowcount == 0
                    continue
                if table_name == "workspaces":
                    continue
                with pytest.raises(DBAPIError) as error, connection.begin_nested():
                    values = _insert_probe_values(
                        table_name, seeded_rows[1][table_name],
                        actors[0], alternate_ids[1]
                    )
                    connection.execute(table.insert().values(**values))
                assert error.value.orig.sqlstate == "42501", (
                    table_name, error.value.orig.sqlstate
                )
            # Cross-workspace parent references must fail even when the child's
            # workspace matches the actor's authorized workspace.
            table = metadata.tables["program_members"]
            with pytest.raises(DBAPIError, match="Tenant parent mismatch") as error, (
                connection.begin_nested()
            ):
                connection.execute(table.insert().values(
                    **_seed_row(table, workspaces[0], actors[0],
                                {"programs": ids[1]["programs"],
                                 "workspace_memberships": ids[0]["workspace_memberships"]},
                                global_template_id)
                ))
            assert error.value.orig.sqlstate == "23503"
            with pytest.raises(DBAPIError, match="Tenant parent mismatch") as error, (
                connection.begin_nested()
            ):
                connection.execute(
                    table.update().where(table.c.id == ids[0]["program_members"]).values(
                        program_id=ids[1]["programs"]
                    )
                )
            assert error.value.orig.sqlstate == "23503"
            assert connection.execute(table.update().where(
                table.c.id == ids[0]["program_members"]
            ).values(assignment_role="Sponsor")).rowcount == 1
            circuit = metadata.tables["llm_circuit_breakers"]
            circuit_id = uuid.uuid4()
            connection.execute(circuit.insert().values(
                id=circuit_id, workspace_id=workspaces[0], provider="legitimate",
                consecutive_failures=0, created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ))
            assert connection.execute(circuit.update().where(
                circuit.c.id == circuit_id
            ).values(consecutive_failures=1)).rowcount == 1
            assert connection.execute(circuit.delete().where(
                circuit.c.id == circuit_id
            )).rowcount == 1
            questions = metadata.tables["question_definitions"]
            values = dict(seeded_rows[0]["question_definitions"])
            values["id"] = uuid.uuid4()
            values["question_key"] = "legitimate-new-question"
            connection.execute(questions.insert().values(**values))
            assert connection.execute(questions.update().where(
                questions.c.id == values["id"]
            ).values(label="Updated label")).rowcount == 1
            assert connection.execute(questions.delete().where(
                questions.c.id == values["id"]
            )).rowcount == 1
    finally:
        admin.dispose()
        app.dispose()
