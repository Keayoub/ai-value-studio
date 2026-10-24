from __future__ import annotations

import json
import uuid

from app.db.models.lifecycle import (
    DimensionScoreRecord,
    ProgramAssignmentRole,
    ProgramMember,
    ScorecardVersion,
    ScoreConfigurationVersion,
    UseCase,
    ValueAssessment,
)
from app.db.session import get_engine
from sqlmodel import Session, select

from backend.tests.conftest import dev_headers
from backend.tests.test_wizard_api import _create_assessment, _fill_assessment


def _scorecard_base(
    *,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
) -> str:
    return (
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}"
        f"/use-cases/{use_case_id}"
    )


def _prepare_assessment(
    dev_client,
    seeded_lifecycle_data,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    headers = dev_headers("consultant-a", roles="Consultant")
    created = _create_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        headers=headers,
    )
    _fill_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=created["assessment"]["id"],
        headers=headers,
    )
    base = _scorecard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    submit = dev_client.post(
        f"{base}/assessments/{created['assessment']['id']}/submit",
        headers=headers,
    )
    assert submit.status_code == 200
    return workspace_id, program_id, use_case_id


def _value_assessment_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "annual_volume": 12000,
        "time_saved_hours": 0.2,
        "hourly_cost": 45,
        "error_reduction_rate": 20,
        "average_error_cost": 85,
        "revenue_capacity_value": 15000,
        "estimated_annual_cost": 25000,
        "time_to_impact_months": 4,
        "primary_kpi": "Temps moyen de qualification",
        "kpi_target": "-30%",
        "confidence": "medium",
        "currency": "EUR",
    }
    payload.update(overrides)
    return payload


def test_value_assessment_scorecard_override_and_history(dev_client, seeded_lifecycle_data) -> None:
    workspace_id, program_id, use_case_id = _prepare_assessment(dev_client, seeded_lifecycle_data)
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    sponsor_headers = dev_headers("sponsor-a", roles="Sponsor")
    base = _scorecard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    initial = dev_client.get(f"{base}/scorecards", headers=consultant_headers)
    assert initial.status_code == 200
    initial_body = initial.json()
    assert initial_body["value_assessment"]["persisted"] is False
    assert initial_body["score_configuration"]["weights"]["business_value"] == 0.25

    put_response = dev_client.put(
        f"{base}/value-assessment",
        json=_value_assessment_payload(),
        headers=consultant_headers,
    )
    assert put_response.status_code == 200
    put_body = put_response.json()
    assert put_body["value_assessment"]["persisted"] is True
    assert put_body["value_assessment"]["net_annual_value"] == 302000.0
    scenario_names = [entry["name"] for entry in put_body["value_assessment"]["scenarios"]]
    assert scenario_names == ["conservative", "baseline", "optimistic"]
    sensitivity_levers = [entry["lever"] for entry in put_body["value_assessment"]["sensitivities"]]
    assert sensitivity_levers == [
        "time_saved_hours",
        "error_reduction_rate",
        "revenue_capacity_value",
    ]

    recalc_response = dev_client.post(
        f"{base}/scorecards/recalculate",
        headers=consultant_headers,
    )
    assert recalc_response.status_code == 200
    recalc_body = recalc_response.json()
    current = recalc_body["current_scorecard"]
    assert current["version"] == 1
    assert len(current["dimensions"]) == 6
    assert round(current["priority_score"], 3) == current["priority_score"]
    assert current["category"] in {
        "Quick Win",
        "Strategic Bet",
        "Foundation",
        "Defer",
        "Reject",
    }

    override_response = dev_client.post(
        f"{base}/scorecards/override",
        json={
            "dimension": "risk_governance",
            "score": 5,
            "reason": "Mitigation formalisée et contrôles RBAC validés.",
        },
        headers=consultant_headers,
    )
    assert override_response.status_code == 200
    override_body = override_response.json()
    assert override_body["current_scorecard"]["version"] == 2
    risk_dimension = next(
        item
        for item in override_body["current_scorecard"]["dimensions"]
        if item["dimension"] == "risk_governance"
    )
    assert risk_dimension["score"] == 5
    assert risk_dimension["is_manual_override"] is True
    assert "Mitigation formalisée" in risk_dimension["override_reason"]
    assert [item["version"] for item in override_body["history"]] == [2, 1]

    sponsor_get = dev_client.get(f"{base}/scorecards", headers=sponsor_headers)
    assert sponsor_get.status_code == 200
    assert sponsor_get.json()["read_only"] is True
    sponsor_put = dev_client.put(
        f"{base}/value-assessment",
        json=put_response.json()["value_assessment"]["input_snapshot"],
        headers=sponsor_headers,
    )
    assert sponsor_put.status_code == 403

    with Session(get_engine()) as session:
        versions = session.exec(
            select(ScorecardVersion)
            .where(ScorecardVersion.use_case_id == use_case_id)
            .order_by(ScorecardVersion.version.asc())
        ).all()
        assert [row.version for row in versions] == [1, 2]
        dimension_rows = session.exec(
            select(DimensionScoreRecord).where(
                DimensionScoreRecord.scorecard_version_id == versions[-1].id
            )
        ).all()
        assert len(dimension_rows) == 6


def test_value_scorecard_mutations_require_effective_consultant_permissions(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id, program_id, use_case_id = _prepare_assessment(dev_client, seeded_lifecycle_data)
    base = _scorecard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    sponsor_headers = dev_headers("sponsor-a", roles="Sponsor")
    contributor_headers = dev_headers("contributor-a", roles="Contributor")
    mismatched_headers = dev_headers("consultant-a", roles="Sponsor")

    for headers in (sponsor_headers, contributor_headers):
        put_response = dev_client.put(
            f"{base}/value-assessment",
            json=_value_assessment_payload(),
            headers=headers,
        )
        assert put_response.status_code == 403

        recalc_response = dev_client.post(f"{base}/scorecards/recalculate", headers=headers)
        assert recalc_response.status_code == 403

        override_response = dev_client.post(
            f"{base}/scorecards/override",
            json={
                "dimension": "risk_governance",
                "score": 5,
                "reason": "Justification documentée.",
            },
            headers=headers,
        )
        assert override_response.status_code == 403

    with Session(get_engine()) as session:
        use_case = session.get(UseCase, use_case_id)
        assert use_case is not None
        use_case.owner_membership_id = seeded_lifecycle_data["consultant_a_membership_id"]
        session.add(use_case)
        session.add(
            ProgramMember(
                workspace_id=workspace_id,
                program_id=program_id,
                membership_id=seeded_lifecycle_data["consultant_a_membership_id"],
                assignment_role=ProgramAssignmentRole.CONTRIBUTOR,
                created_by_subject_id=use_case.created_by_subject_id,
            )
        )
        session.commit()

    mismatch_get = dev_client.get(f"{base}/scorecards", headers=mismatched_headers)
    assert mismatch_get.status_code == 200
    assert mismatch_get.json()["read_only"] is True
    assert mismatch_get.json()["can_override"] is False

    put_response = dev_client.put(
        f"{base}/value-assessment",
        json=_value_assessment_payload(),
        headers=mismatched_headers,
    )
    assert put_response.status_code == 403

    recalc_response = dev_client.post(f"{base}/scorecards/recalculate", headers=mismatched_headers)
    assert recalc_response.status_code == 403

    override_response = dev_client.post(
        f"{base}/scorecards/override",
        json={
            "dimension": "risk_governance",
            "score": 5,
            "reason": "Justification documentée.",
        },
        headers=mismatched_headers,
    )
    assert override_response.status_code == 403


def test_value_assessment_revisions_preserve_historical_scorecards_and_invalidate_stale_current(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id, program_id, use_case_id = _prepare_assessment(dev_client, seeded_lifecycle_data)
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    base = _scorecard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    first_put = dev_client.put(
        f"{base}/value-assessment",
        json=_value_assessment_payload(),
        headers=consultant_headers,
    )
    assert first_put.status_code == 200
    first_value_assessment_id = uuid.UUID(first_put.json()["value_assessment"]["id"])

    first_recalc = dev_client.post(f"{base}/scorecards/recalculate", headers=consultant_headers)
    assert first_recalc.status_code == 200
    first_scorecard = first_recalc.json()["current_scorecard"]
    assert first_scorecard is not None
    first_scorecard_id = uuid.UUID(first_scorecard["id"])
    assert first_scorecard["value_assessment_id"] == str(first_value_assessment_id)
    assert first_scorecard["input_snapshot"]["value_inputs"]["annual_volume"] == 12000.0

    second_put = dev_client.put(
        f"{base}/value-assessment",
        json=_value_assessment_payload(
            annual_volume=8000,
            time_saved_hours=0.1,
            revenue_capacity_value=5000,
        ),
        headers=consultant_headers,
    )
    assert second_put.status_code == 200
    second_body = second_put.json()
    second_value_assessment_id = uuid.UUID(second_body["value_assessment"]["id"])
    assert second_value_assessment_id != first_value_assessment_id
    assert second_body["current_scorecard"] is None
    assert second_body["history"][0]["id"] == str(first_scorecard_id)

    after_update = dev_client.get(f"{base}/scorecards", headers=consultant_headers)
    assert after_update.status_code == 200
    after_update_body = after_update.json()
    assert after_update_body["current_scorecard"] is None
    assert after_update_body["history"][0]["id"] == str(first_scorecard_id)
    assert after_update_body["value_assessment"]["id"] == str(second_value_assessment_id)

    with Session(get_engine()) as session:
        use_case = session.get(UseCase, use_case_id)
        assert use_case is not None
        assert use_case.priority_score is None
        assert use_case.category is None
        assert use_case.score_version is None
        assert use_case.confidence_level is None

    second_recalc = dev_client.post(f"{base}/scorecards/recalculate", headers=consultant_headers)
    assert second_recalc.status_code == 200
    second_scorecard = second_recalc.json()["current_scorecard"]
    assert second_scorecard is not None
    assert second_scorecard["version"] == 2
    assert second_scorecard["value_assessment_id"] == str(second_value_assessment_id)
    assert second_recalc.json()["history"][1]["id"] == str(first_scorecard_id)
    assert (
        second_recalc.json()["history"][1]["input_snapshot"]["value_assessment_id"]
        == str(first_value_assessment_id)
    )

    with Session(get_engine()) as session:
        use_case = session.get(UseCase, use_case_id)
        assert use_case is not None
        assert float(use_case.priority_score) == second_scorecard["priority_score"]
        assert use_case.category == second_scorecard["category"]
        assert use_case.score_version == 2
        assert use_case.confidence_level == second_scorecard["confidence_level"]
        scorecard_versions = session.exec(
            select(ScorecardVersion)
            .where(ScorecardVersion.use_case_id == use_case_id)
            .order_by(ScorecardVersion.version.asc())
        ).all()
        assert [row.version for row in scorecard_versions] == [1, 2]
        assert scorecard_versions[0].value_assessment_id == first_value_assessment_id
        assert scorecard_versions[1].value_assessment_id == second_value_assessment_id

        revisions = session.exec(
            select(ValueAssessment)
            .where(
                ValueAssessment.use_case_id == use_case_id,
                ValueAssessment.assessment_version_id
                == scorecard_versions[0].assessment_version_id,
            )
            .order_by(ValueAssessment.revision.asc())
        ).all()
        assert [row.revision for row in revisions] == [1, 2]
        assert revisions[0].id == first_value_assessment_id
        assert revisions[1].id == second_value_assessment_id
        assert float(revisions[0].annual_volume) == 12000.0
        assert float(revisions[1].annual_volume) == 8000.0

        historical_scorecard = session.get(ScorecardVersion, first_scorecard_id)
        assert historical_scorecard is not None
        assert historical_scorecard.value_assessment_id == first_value_assessment_id
        assert historical_scorecard.input_snapshot_json["value_inputs"]["annual_volume"] == 12000.0


def test_value_scorecard_rejects_invalid_payloads_and_override_reason(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id, program_id, use_case_id = _prepare_assessment(dev_client, seeded_lifecycle_data)
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    base = _scorecard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    invalid_rate = dev_client.put(
        f"{base}/value-assessment",
        json=_value_assessment_payload(error_reduction_rate=101),
        headers=consultant_headers,
    )
    assert invalid_rate.status_code == 422

    for field, value in (("annual_volume", float("nan")), ("hourly_cost", float("inf"))):
        # Send the literal JSON tokens to exercise server validation regardless of
        # whether the installed HTTPX version rejects nonfinite json= values locally.
        invalid = dev_client.put(
            f"{base}/value-assessment",
            content=json.dumps(_value_assessment_payload(**{field: value})),
            headers={**consultant_headers, "Content-Type": "application/json"},
        )
        assert invalid.status_code == 422
        assert field in invalid.text
        with Session(get_engine()) as session:
            assert session.exec(
                select(ValueAssessment).where(ValueAssessment.use_case_id == use_case_id)
            ).all() == []

    blank_override_reason = dev_client.post(
        f"{base}/scorecards/override",
        json={
            "dimension": "risk_governance",
            "score": 4,
            "reason": "   ",
        },
        headers=consultant_headers,
    )
    assert blank_override_reason.status_code == 422
    scorecards = dev_client.get(f"{base}/scorecards", headers=consultant_headers)
    assert scorecards.status_code == 200
    assert scorecards.json()["value_assessment"]["persisted"] is False


def test_value_scorecard_rejects_invalid_configuration_and_cross_tenant_access(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id, program_id, use_case_id = _prepare_assessment(dev_client, seeded_lifecycle_data)
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    base = _scorecard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    dev_client.get(f"{base}/scorecards", headers=consultant_headers)
    with Session(get_engine()) as session:
        config = session.exec(
            select(ScoreConfigurationVersion).where(
                ScoreConfigurationVersion.workspace_id == workspace_id,
                ScoreConfigurationVersion.is_active.is_(True),
            )
        ).first()
        assert config is not None
        config.weights_json = {
            "business_value": 0.40,
            "current_friction": 0.15,
            "data_feasibility": 0.15,
            "technical_feasibility": 0.15,
            "adoption_potential": 0.10,
        }
        session.add(config)
        session.commit()

    invalid_recalc = dev_client.post(f"{base}/scorecards/recalculate", headers=consultant_headers)
    assert invalid_recalc.status_code == 409
    assert "Invalid active score configuration" in invalid_recalc.json()["detail"]

    workspace_b_id = seeded_lifecycle_data["workspace_b_id"]
    program_b_id = seeded_lifecycle_data["program_b_id"]
    use_case_b_id = seeded_lifecycle_data["use_case_b_id"]
    cross_tenant = dev_client.get(
        _scorecard_base(
            workspace_id=workspace_id,
            program_id=program_b_id,
            use_case_id=use_case_b_id,
        )
        + "/scorecards",
        headers=consultant_headers,
    )
    assert cross_tenant.status_code == 404
    forbidden_workspace = dev_client.get(
        _scorecard_base(
            workspace_id=workspace_b_id,
            program_id=program_b_id,
            use_case_id=use_case_b_id,
        )
        + "/scorecards",
        headers=consultant_headers,
    )
    assert forbidden_workspace.status_code == 404
