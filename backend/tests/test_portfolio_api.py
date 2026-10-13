from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.db.models.lifecycle import (
    Answer,
    AnswerSource,
    AssessmentStatus,
    AssessmentVersion,
    DimensionScoreRecord,
    Program,
    QuestionnaireTemplateVersion,
    ScorecardVersion,
    ScoreConfigurationVersion,
    ScoreDimension,
    UseCase,
    UseCaseStatus,
    ValueAssessment,
)
from app.db.session import get_engine
from sqlmodel import Session, select

from backend.tests.conftest import dev_headers


@dataclass(slots=True)
class PortfolioSnapshot:
    title: str
    category: str
    business_value: int
    readiness: float
    risk: str
    effort_band: str
    net_annual_value: float
    department: str
    status: UseCaseStatus
    currency: str = "EUR"


def _portfolio_base(workspace_id: uuid.UUID) -> str:
    return f"/api/v1/workspaces/{workspace_id}/portfolio"


def _risk_governance_score(risk: str) -> int:
    return {
        "Low": 5,
        "Medium": 4,
        "High": 3,
        "Critical": 2,
    }[risk]


def _ensure_score_configuration(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    created_by_subject_id: uuid.UUID,
) -> ScoreConfigurationVersion:
    configuration = session.exec(
        select(ScoreConfigurationVersion).where(
            ScoreConfigurationVersion.workspace_id == workspace_id,
            ScoreConfigurationVersion.is_active.is_(True),
        )
    ).first()
    if configuration is not None:
        return configuration
    configuration = ScoreConfigurationVersion(
        workspace_id=workspace_id,
        version=1,
        is_active=True,
        weights_json={
            "business_value": 0.25,
            "current_friction": 0.15,
            "data_feasibility": 0.15,
            "technical_feasibility": 0.15,
            "adoption_potential": 0.10,
            "risk_governance": 0.20,
        },
        thresholds_json={
            "quick_win_priority_min": 4.0,
            "quick_win_readiness_min": 3.8,
            "quick_win_governance_min": 3,
            "strategic_bet_priority_min": 4.0,
            "foundation_readiness_max": 3.0,
            "reject_priority_max": 2.8,
            "reject_governance_max": 2,
        },
        created_by_subject_id=created_by_subject_id,
    )
    session.add(configuration)
    session.flush()
    return configuration


def _persist_snapshot(
    session: Session,
    *,
    use_case: UseCase,
    snapshot: PortfolioSnapshot,
) -> None:
    template = session.exec(
        select(QuestionnaireTemplateVersion)
        .where(QuestionnaireTemplateVersion.is_active.is_(True))
        .order_by(QuestionnaireTemplateVersion.workspace_id.is_not(None).desc())
    ).first()
    assert template is not None
    configuration = _ensure_score_configuration(
        session,
        workspace_id=use_case.workspace_id,
        created_by_subject_id=use_case.created_by_subject_id,
    )
    assessment = AssessmentVersion(
        workspace_id=use_case.workspace_id,
        use_case_id=use_case.id,
        version=1,
        template_version_id=template.id,
        status=AssessmentStatus.SUBMITTED,
        submitted_by_subject_id=use_case.created_by_subject_id,
        submitted_at=datetime.now(UTC),
        created_by_subject_id=use_case.created_by_subject_id,
    )
    session.add(assessment)
    session.flush()

    session.add(
        Answer(
            workspace_id=use_case.workspace_id,
            assessment_version_id=assessment.id,
            question_key="effort_band",
            value_data_json=snapshot.effort_band,
            entered_by_subject_id=use_case.created_by_subject_id,
            source=AnswerSource.HUMAN,
        )
    )

    value_assessment = ValueAssessment(
        workspace_id=use_case.workspace_id,
        use_case_id=use_case.id,
        assessment_version_id=assessment.id,
        revision=1,
        annual_volume=1000,
        time_saved_hours=0.1,
        hourly_cost=50,
        error_reduction_rate=10,
        average_error_cost=75,
        revenue_capacity_value=max(snapshot.net_annual_value, 0),
        estimated_annual_cost=0,
        time_to_impact_months=3,
        primary_kpi="Temps de cycle",
        kpi_target="-20%",
        confidence="medium",
        currency=snapshot.currency,
        calculation_version="portfolio-test",
        annual_time_value=max(snapshot.net_annual_value, 0),
        error_avoidance_value=0,
        gross_value=max(snapshot.net_annual_value, 0),
        net_annual_value=snapshot.net_annual_value,
        npv_3y=snapshot.net_annual_value * 2,
        payback_months=12,
        input_snapshot_json={},
        source_snapshot_json={"question_sources": {"effort_band": snapshot.effort_band}},
        scenarios_json=[],
        sensitivities_json=[],
        created_by_subject_id=use_case.created_by_subject_id,
    )
    session.add(value_assessment)
    session.flush()

    scorecard = ScorecardVersion(
        workspace_id=use_case.workspace_id,
        use_case_id=use_case.id,
        assessment_version_id=assessment.id,
        value_assessment_id=value_assessment.id,
        score_configuration_version_id=configuration.id,
        version=1,
        priority_score=4.125,
        readiness_average=snapshot.readiness,
        category=snapshot.category,
        risk_profile=snapshot.risk,
        confidence_level="medium",
        calculation_version="portfolio-test",
        input_snapshot_json={},
        formula_snapshot_json={},
        created_by_subject_id=use_case.created_by_subject_id,
    )
    session.add(scorecard)
    session.flush()

    rounded_readiness = max(1, min(5, round(snapshot.readiness)))
    dimension_scores = {
        ScoreDimension.BUSINESS_VALUE: snapshot.business_value,
        ScoreDimension.CURRENT_FRICTION: 3,
        ScoreDimension.DATA_FEASIBILITY: rounded_readiness,
        ScoreDimension.TECHNICAL_FEASIBILITY: rounded_readiness,
        ScoreDimension.ADOPTION_POTENTIAL: rounded_readiness,
        ScoreDimension.RISK_GOVERNANCE: _risk_governance_score(snapshot.risk),
    }
    for dimension, score in dimension_scores.items():
        session.add(
            DimensionScoreRecord(
                workspace_id=use_case.workspace_id,
                scorecard_version_id=scorecard.id,
                dimension=dimension,
                weight=configuration.weights_json[dimension.value],
                score=score,
                source="deterministic",
                justification=f"{dimension.value} snapshot",
                confidence="medium",
                created_by_subject_id=use_case.created_by_subject_id,
            )
        )

    use_case.title = snapshot.title
    use_case.department = snapshot.department
    use_case.status = snapshot.status
    use_case.recommendation = "Pilot"
    use_case.category = snapshot.category
    use_case.priority_score = 4.125
    use_case.score_version = 1
    use_case.confidence_level = "medium"
    use_case.current_assessment_version = 1
    session.add(use_case)


def _seed_portfolio_cases(dev_client, seeded_lifecycle_data) -> dict[str, object]:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_a_id = seeded_lifecycle_data["use_case_a_id"]
    other_use_case_a_id = seeded_lifecycle_data["other_use_case_a_id"]

    with Session(get_engine()) as session:
        workspace_program = session.get(Program, program_id)
        use_case_a = session.get(UseCase, use_case_a_id)
        assert workspace_program is not None
        assert use_case_a is not None

        extra_membership = seeded_lifecycle_data["extra_a_membership_id"]

        created_by_subject_id = use_case_a.created_by_subject_id
        hidden_program = Program(
            workspace_id=workspace_program.workspace_id,
            name="Programme invisible",
            strategic_objective="Programme hors portee du sponsor et du contributeur.",
            consultant_membership_id=seeded_lifecycle_data["consultant_a_membership_id"],
            created_by_subject_id=created_by_subject_id,
        )
        session.add(hidden_program)
        session.flush()

        visible_strategic = UseCase(
            workspace_id=workspace_program.workspace_id,
            program_id=workspace_program.id,
            title="Pari strategique",
            department="Operations",
            owner_membership_id=seeded_lifecycle_data["sponsor_unassigned_a_membership_id"],
            created_by_subject_id=created_by_subject_id,
        )
        visible_foundation = UseCase(
            workspace_id=workspace_program.workspace_id,
            program_id=workspace_program.id,
            title="Fondation data",
            department="Finance",
            owner_membership_id=seeded_lifecycle_data["sponsor_unassigned_a_membership_id"],
            created_by_subject_id=created_by_subject_id,
        )
        visible_defer = UseCase(
            workspace_id=workspace_program.workspace_id,
            program_id=workspace_program.id,
            title="Differe capacite",
            department="Operations",
            owner_membership_id=seeded_lifecycle_data["sponsor_unassigned_a_membership_id"],
            created_by_subject_id=created_by_subject_id,
        )
        hidden_use_case = UseCase(
            workspace_id=workspace_program.workspace_id,
            program_id=hidden_program.id,
            title="Programme masque",
            department="Juridique",
            owner_membership_id=extra_membership,
            created_by_subject_id=created_by_subject_id,
        )
        session.add(visible_strategic)
        session.add(visible_foundation)
        session.add(visible_defer)
        session.add(hidden_use_case)
        session.commit()

        strategic_id = visible_strategic.id
        foundation_id = visible_foundation.id
        defer_id = visible_defer.id
        hidden_program_id = hidden_program.id
        hidden_use_case_id = hidden_use_case.id

    with Session(get_engine()) as session:
        for use_case_id, snapshot in (
            (
                use_case_a_id,
                PortfolioSnapshot(
                    title="Quick win operations",
                    category="Quick Win",
                    business_value=5,
                    readiness=3.8,
                    risk="Low",
                    effort_band="low",
                    net_annual_value=302000,
                    department="Operations",
                    status=UseCaseStatus.APPROVED,
                ),
            ),
            (
                other_use_case_a_id,
                PortfolioSnapshot(
                    title="Cas sponsor visible",
                    category="Reject",
                    business_value=2,
                    readiness=3.1,
                    risk="Critical",
                    effort_band="high",
                    net_annual_value=-5000,
                    department="Finance",
                    status=UseCaseStatus.REJECTED,
                ),
            ),
            (
                strategic_id,
                PortfolioSnapshot(
                    title="Pari strategique",
                    category="Strategic Bet",
                    business_value=5,
                    readiness=3.79,
                    risk="High",
                    effort_band="high",
                    net_annual_value=120000,
                    department="Operations",
                    status=UseCaseStatus.SUBMITTED,
                ),
            ),
            (
                foundation_id,
                PortfolioSnapshot(
                    title="Fondation data",
                    category="Foundation",
                    business_value=3,
                    readiness=2.99,
                    risk="Medium",
                    effort_band="medium",
                    currency="USD",
                    net_annual_value=45000,
                    department="Finance",
                    status=UseCaseStatus.CHANGES_REQUESTED,
                ),
            ),
            (
                defer_id,
                PortfolioSnapshot(
                    title="Differe capacite",
                    category="Defer",
                    business_value=3,
                    readiness=3.4,
                    risk="Medium",
                    effort_band="medium",
                    net_annual_value=10000,
                    department="Operations",
                    status=UseCaseStatus.IN_PROGRESS,
                ),
            ),
            (
                hidden_use_case_id,
                PortfolioSnapshot(
                    title="Programme masque",
                    category="Quick Win",
                    business_value=5,
                    readiness=4.2,
                    risk="Low",
                    effort_band="low",
                    net_annual_value=60000,
                    department="Juridique",
                    status=UseCaseStatus.APPROVED,
                ),
            ),
        ):
            use_case = session.get(UseCase, use_case_id)
            assert use_case is not None
            _persist_snapshot(session, use_case=use_case, snapshot=snapshot)
        session.commit()

    return {
        "workspace_id": workspace_id,
        "program_id": program_id,
        "hidden_program_id": hidden_program_id,
        "use_case_a_id": use_case_a_id,
    }

def test_portfolio_returns_scored_snapshots_with_matrix_fields(
    dev_client, seeded_lifecycle_data
) -> None:
    seeded = _seed_portfolio_cases(dev_client, seeded_lifecycle_data)

    response = dev_client.get(
        _portfolio_base(seeded["workspace_id"]),
        headers=dev_headers("consultant-a", roles="Consultant"),
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["category"] for item in body["items"]] == [
        "Quick Win",
        "Quick Win",
        "Strategic Bet",
        "Defer",
        "Foundation",
        "Reject",
    ]
    quick_win = next(
        item for item in body["items"] if item["use_case_title"] == "Quick win operations"
    )
    assert quick_win["matrix_x"] == 3.8
    assert quick_win["matrix_y"] == 5
    assert quick_win["risk_shape"] == "circle"
    assert quick_win["risk_pattern"] == "solid"
    assert quick_win["effort_band"] == "low"
    assert quick_win["effort_label_fr"] == "Effort faible"
    assert "valeur ≥ 4" in quick_win["category_explanation_fr"]
    assert "gouvernance 5/5" in quick_win["category_explanation_fr"]
    assert quick_win["net_annual_value"] == 302000.0
    strategic = next(
        item for item in body["items"] if item["use_case_title"] == "Pari strategique"
    )
    assert "valeur ≥ 4 ou priorité ≥ 4" in strategic["category_explanation_fr"]
    assert "readiness ≥ 3,0 et < 3,8" in strategic["category_explanation_fr"]
    foundation = next(item for item in body["items"] if item["use_case_title"] == "Fondation data")
    assert foundation["currency"] == "USD"
    assert "readiness < 3,0" in foundation["category_explanation_fr"]
    assert body["summary"]["total_items"] == 6
    assert body["summary"]["category_counts"]["Reject"] == 1
    assert {item["name"] for item in body["available_filters"]["programs"]} == {
        "Programme A",
        "Programme invisible",
    }
    assert {item["value"] for item in body["available_filters"]["risks"]} == {
        "Low",
        "Medium",
        "High",
        "Critical",
    }


def test_portfolio_filters_server_side(dev_client, seeded_lifecycle_data) -> None:
    seeded = _seed_portfolio_cases(dev_client, seeded_lifecycle_data)
    base = _portfolio_base(seeded["workspace_id"])
    headers = dev_headers("consultant-a", roles="Consultant")

    status_filtered = dev_client.get(
        base,
        params={"status": "Approved"},
        headers=headers,
    )
    assert status_filtered.status_code == 200
    assert {item["use_case_title"] for item in status_filtered.json()["items"]} == {
        "Quick win operations",
        "Programme masque",
    }

    department_filtered = dev_client.get(
        base,
        params={"department": "Finance"},
        headers=headers,
    )
    assert department_filtered.status_code == 200
    assert {item["category"] for item in department_filtered.json()["items"]} == {
        "Foundation",
        "Reject",
    }

    risk_filtered = dev_client.get(
        base,
        params={"risk": "Medium"},
        headers=headers,
    )
    assert risk_filtered.status_code == 200
    assert [item["category"] for item in risk_filtered.json()["items"]] == [
        "Defer",
        "Foundation",
    ]

    program_filtered = dev_client.get(
        base,
        params={"program_id": str(seeded["program_id"])},
        headers=headers,
    )
    assert program_filtered.status_code == 200
    assert program_filtered.json()["summary"]["total_items"] == 5


def test_portfolio_honors_sponsor_contributor_scope_and_hides_inaccessible_program_filters(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    seeded = _seed_portfolio_cases(dev_client, seeded_lifecycle_data)
    base = _portfolio_base(seeded["workspace_id"])

    sponsor_response = dev_client.get(
        base,
        headers=dev_headers("sponsor-a", roles="Sponsor"),
    )
    assert sponsor_response.status_code == 200
    sponsor_titles = [item["use_case_title"] for item in sponsor_response.json()["items"]]
    assert "Programme masque" not in sponsor_titles
    assert len(sponsor_titles) == 5

    contributor_response = dev_client.get(
        base,
        headers=dev_headers("contributor-a", roles="Contributor"),
    )
    assert contributor_response.status_code == 200
    contributor_body = contributor_response.json()
    assert [item["use_case_id"] for item in contributor_body["items"]] == [
        str(seeded["use_case_a_id"])
    ]

    hidden_program = dev_client.get(
        base,
        params={"program_id": str(seeded["hidden_program_id"])},
        headers=dev_headers("sponsor-a", roles="Sponsor"),
    )
    assert hidden_program.status_code == 200
    hidden_body = hidden_program.json()
    assert hidden_body["items"] == []
    assert hidden_body["summary"]["total_items"] == 0
    assert hidden_body["applied_filters"]["program_id"] is None
    assert {item["name"] for item in hidden_body["available_filters"]["programs"]} == {
        "Programme A"
    }
