from __future__ import annotations

import uuid

from app.audit.models import AuditEvent
from app.db.models.identity import IdentitySubject
from app.db.models.lifecycle import (
    Answer,
    AssessmentVersion,
    Hypothesis,
    HypothesisKind,
    HypothesisStatus,
    QuestionDefinition,
    UseCase,
)
from app.db.session import get_engine
from sqlmodel import Session, select

from backend.tests.conftest import dev_headers


def _wizard_base(
    *,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
) -> str:
    return (
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}"
        f"/use-cases/{use_case_id}/assessments"
    )


def _create_assessment(
    dev_client,
    *,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    headers: dict[str, str],
    interview_mode: bool = False,
    respondent_membership_id: uuid.UUID | None = None,
) -> dict[str, object]:
    response = dev_client.post(
        _wizard_base(workspace_id=workspace_id, program_id=program_id, use_case_id=use_case_id),
        json={
            "interview_mode": interview_mode,
            "respondent_membership_id": str(respondent_membership_id)
            if respondent_membership_id
            else None,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _put_answer(
    dev_client,
    *,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    assessment_id: uuid.UUID | str,
    question_key: str,
    value: object,
    headers: dict[str, str],
    captured_for_membership_id: uuid.UUID | None = None,
) -> None:
    base_path = _wizard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    response = dev_client.put(
        f"{base_path}/{assessment_id}/answers/{question_key}",
        json={
            "value": value,
            "captured_for_membership_id": str(captured_for_membership_id)
            if captured_for_membership_id
            else None,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text


def _valid_answers() -> dict[str, object]:
    return {
        "target_process": "Traiter les dossiers entrants avec une qualification cohérente.",
        "team_name": "Opérations sinistres",
        "trigger_event": "Réception d'un nouveau dossier",
        "process_steps": ["Réception", "Contrôle", "Qualification", "Affectation"],
        "systems_involved": ["CRM", "GED", "Portail client"],
        "annual_volume": 12000,
        "duration_minutes_per_occurrence": 25.0,
        "problem_statement": "Le tri et le contrôle initial sont trop lents et irréguliers.",
        "delay_cost_risk_causes": (
            "Documents incomplets, relectures multiples et règles dispersées."
        ),
        "error_points": "Pièces manquantes non détectées et mauvaise affectation initiale.",
        "missing_knowledge": "Variantes de dossiers rares.",
        "impact_type": "quantified",
        "impact_statement": "Le délai moyen augmente de 2 jours ouvrés.",
        "cost_of_inaction": "Surcharge opérationnelle et insatisfaction client.",
        "reason_now": "Hausse du volume et pression sur les SLA.",
        "supporting_evidence": "Mesures mensuelles 2026 et retours des gestionnaires.",
        "ai_task": "Analyser le dossier, détecter les pièces manquantes et proposer la suite.",
        "ai_inputs": "Dossier PDF, métadonnées et pièces justificatives.",
        "ai_outputs": "Résumé, anomalies et action recommandée.",
        "autonomy_level": "recommend",
        "human_validation_policy": "mandatory",
        "supported_languages": ["Français", "Anglais"],
        "prohibited_behaviour": "Aucune décision finale sans validation humaine.",
        "solution_pattern": "generic",
        "time_saved_hours": 0.2,
        "hourly_cost": 45.0,
        "error_reduction_rate": 20.0,
        "average_error_cost": 85.0,
        "revenue_capacity_impact": 15000.0,
        "estimated_annual_cost": 25000.0,
        "time_to_impact_months": 4,
        "primary_kpi": "Temps moyen de qualification",
        "kpi_target": "-30%",
        "hypothesis_confidence": "medium",
        "value_hypothesis": "L'automatisation assistée réduit les relectures manuelles.",
        "data_sources": ["GED", "CRM", "Exports d'activité"],
        "data_owner": "Responsable opérations",
        "data_availability": "available",
        "data_type": "document",
        "data_quality_score": 3,
        "pilot_accessibility": "ready",
        "sensitive_data_flag": "personal",
        "connectors_needed": "Connecteur GED et lecture CRM.",
        "integration_dependencies": "GED, CRM et annuaire des équipes.",
        "deployment_environment": "customer_vpc",
        "latency_availability_expectation": "Réponse en moins de 30 secondes.",
        "team_skills": "Équipe BA et support applicatif disponibles.",
        "support_owner": "Lead opérations",
        "training_needs": "Formation d'une demi-journée.",
        "dependency_statement": "Validation sécurité et accès GED.",
        "effort_band": "medium",
        "bad_answer_impact": "medium",
        "affected_person_decision": False,
        "explanation_required": True,
        "human_validation_required": "mandatory",
        "data_boundary": "internal_only",
        "audit_logging_requirement": True,
        "access_model": "rbac",
        "compliance_constraints": "Journalisation et conservation 12 mois.",
        "risk_owner": "Sponsor métier",
        "risk_acceptance": True,
        "risk_hypothesis": "Le taux de faux positifs doit rester sous 5%.",
        "preliminary_recommendation": "Pilot",
        "review_notes": "Périmètre limité au tri initial pour le pilote.",
    }


def _fill_assessment(
    dev_client,
    *,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    assessment_id: uuid.UUID | str,
    headers: dict[str, str],
) -> None:
    for question_key, value in _valid_answers().items():
        _put_answer(
            dev_client,
            workspace_id=workspace_id,
            program_id=program_id,
            use_case_id=use_case_id,
            assessment_id=assessment_id,
            question_key=question_key,
            value=value,
            headers=headers,
        )


def test_wizard_create_answer_validate_submit_and_reopen(dev_client, seeded_lifecycle_data) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    headers = dev_headers("consultant-a", roles="Consultant")
    base_path = _wizard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    created = _create_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        headers=headers,
    )
    assessment_id = created["assessment"]["id"]
    assert created["template"]["template_key"] == "baseline-fr"
    assert created["template"]["steps"][0]["available"] is False
    assert created["assessment"]["status"] == "Draft"
    assert created["derived"]["step4_preview"] is None

    _fill_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=assessment_id,
        headers=headers,
    )

    current = dev_client.get(
        f"{base_path}/current",
        headers=headers,
    )
    assert current.status_code == 200
    current_body = current.json()
    assert current_body["derived"]["step4_preview"] == {
        "annual_time_value": 108000.0,
        "error_avoidance_value": 204000.0,
        "gross_value": 327000.0,
        "net_value": 302000.0,
    }
    assert current_body["derived"]["risk_profile"] == "Medium"

    validate_response = dev_client.post(
        f"{base_path}/{assessment_id}/validate-step/8",
        headers=headers,
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["is_valid"] is True

    submit_response = dev_client.post(
        f"{base_path}/{assessment_id}/submit",
        headers=headers,
    )
    assert submit_response.status_code == 200
    submitted = submit_response.json()["submitted"]
    assert submitted["assessment"]["status"] == "Submitted"
    assert submitted["assessment"]["can_edit"] is False
    assert submitted["assessment"]["can_submit"] is False

    with Session(get_engine()) as session:
        assessment = session.get(AssessmentVersion, uuid.UUID(assessment_id))
        assert assessment is not None
        assert assessment.submission_snapshot_json is not None
        assert (
            assessment.submission_snapshot_json["derived"]["step4_preview"]["net_value"] == 302000.0
        )
        assert session.exec(
            select(Hypothesis).where(Hypothesis.assessment_version_id == assessment.id)
        ).all()
        use_case = session.get(UseCase, use_case_id)
        assert use_case is not None
        assert use_case.current_assessment_version == 1

    immutable_response = dev_client.put(
        f"{base_path}/{assessment_id}/answers/problem_statement",
        json={"value": "Attempted mutation after submit"},
        headers=headers,
    )
    assert immutable_response.status_code == 409

    locked_reopen = dev_client.post(base_path, json={}, headers=headers)
    assert locked_reopen.status_code == 409
    assert "locked until the sponsor requests changes" in locked_reopen.json()["detail"]


def test_wizard_enforces_conditional_validation_rules(dev_client, seeded_lifecycle_data) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    headers = dev_headers("consultant-a", roles="Consultant")
    base_path = _wizard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    created = _create_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        headers=headers,
    )
    assessment_id = created["assessment"]["id"]

    _put_answer(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=assessment_id,
        question_key="solution_pattern",
        value="ai_case_processing",
        headers=headers,
    )
    step3 = dev_client.post(
        f"{base_path}/{assessment_id}/validate-step/3",
        headers=headers,
    )
    assert step3.status_code == 200
    step3_errors = {error["question_key"] for error in step3.json()["errors"]}
    assert "case_processing_dossier_type" in step3_errors
    assert "case_processing_sensitive_flags" in step3_errors

    _put_answer(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=assessment_id,
        question_key="data_availability",
        value="unavailable",
        headers=headers,
    )
    step5 = dev_client.post(
        f"{base_path}/{assessment_id}/validate-step/5",
        headers=headers,
    )
    assert any(
        error["question_key"] == "data_unavailable_reason" for error in step5.json()["errors"]
    )
    current = dev_client.get(f"{base_path}/current", headers=headers)
    assert current.status_code == 200
    data_step = next(step for step in current.json()["template"]["steps"] if step["index"] == 5)
    data_questions = {question["key"]: question for question in data_step["questions"]}
    assert data_questions["data_quality_score"]["visible"] is False
    assert data_questions["pilot_accessibility"]["visible"] is False

    hidden_put = dev_client.put(
        f"{base_path}/{assessment_id}/answers/data_quality_score",
        json={"value": 3},
        headers=headers,
    )
    assert hidden_put.status_code == 400

    _put_answer(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=assessment_id,
        question_key="bad_answer_impact",
        value="critical",
        headers=headers,
    )
    _put_answer(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=assessment_id,
        question_key="affected_person_decision",
        value=True,
        headers=headers,
    )
    _put_answer(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=assessment_id,
        question_key="human_validation_required",
        value="sample_based",
        headers=headers,
    )
    step7 = dev_client.post(
        f"{base_path}/{assessment_id}/validate-step/7",
        headers=headers,
    )
    assert {error["question_key"] for error in step7.json()["errors"]} >= {
        "mitigation_plan",
        "human_validation_required",
    }
    assert step7.json()["derived"]["risk_profile"] == "Critical"


def test_contributor_and_sponsor_permissions_are_enforced(
    dev_client, seeded_lifecycle_data
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    contributor_headers = dev_headers("contributor-a", roles="Contributor")
    sponsor_headers = dev_headers("sponsor-a", roles="Sponsor")
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    base_path = _wizard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    created = _create_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        headers=consultant_headers,
    )
    assessment_id = created["assessment"]["id"]

    contributor_edit = dev_client.put(
        f"{base_path}/{assessment_id}/answers/problem_statement",
        json={"value": "Le tri manuel ralentit le traitement."},
        headers=contributor_headers,
    )
    assert contributor_edit.status_code == 200

    contributor_forbidden = dev_client.put(
        f"{base_path}/{assessment_id}/answers/time_saved_hours",
        json={"value": 0.25},
        headers=contributor_headers,
    )
    assert contributor_forbidden.status_code == 403

    sponsor_view = dev_client.get(
        f"{base_path}/current",
        headers=sponsor_headers,
    )
    assert sponsor_view.status_code == 200
    sponsor_edit = dev_client.put(
        f"{base_path}/{assessment_id}/answers/problem_statement",
        json={"value": "Tentative sponsor"},
        headers=sponsor_headers,
    )
    assert sponsor_edit.status_code == 403

    sponsor_validate = dev_client.post(
        f"{base_path}/{assessment_id}/validate-step/1",
        headers=sponsor_headers,
    )
    assert sponsor_validate.status_code == 403


def test_interview_capture_attribution_is_recorded(dev_client, seeded_lifecycle_data) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    respondent_membership_id = seeded_lifecycle_data["contributor_a_membership_id"]
    consultant_headers = dev_headers("consultant-a", roles="Consultant")

    created = _create_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        headers=consultant_headers,
        interview_mode=True,
        respondent_membership_id=respondent_membership_id,
    )
    assessment_id = uuid.UUID(created["assessment"]["id"])

    _put_answer(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=assessment_id,
        question_key="problem_statement",
        value="Le répondant décrit une qualification initiale trop lente.",
        headers=consultant_headers,
    )

    with Session(get_engine()) as session:
        answer = session.exec(
            select(Answer).where(
                Answer.assessment_version_id == assessment_id,
                Answer.question_key == "problem_statement",
            )
        ).one()
        consultant_identity = session.exec(
            select(IdentitySubject).where(IdentitySubject.subject == "dev:consultant-a")
        ).one()
        assert answer.captured_for_membership_id == respondent_membership_id
        assert answer.entered_by_subject_id == consultant_identity.id


def test_only_current_draft_version_can_be_edited_or_submitted(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    base_path = _wizard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    first_draft = _create_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        headers=consultant_headers,
    )
    first_assessment_id = first_draft["assessment"]["id"]
    _put_answer(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=first_assessment_id,
        question_key="problem_statement",
        value="La première version brouillon ne doit plus être modifiable.",
        headers=consultant_headers,
    )

    second_draft = dev_client.post(
        base_path,
        json={"force_new_version": True},
        headers=consultant_headers,
    )
    assert second_draft.status_code == 201
    second_assessment_id = second_draft.json()["assessment"]["id"]

    stale_draft = dev_client.get(
        f"{base_path}/{first_assessment_id}",
        headers=consultant_headers,
    )
    assert stale_draft.status_code == 200
    assert stale_draft.json()["assessment"]["status"] == "Draft"
    assert stale_draft.json()["assessment"]["can_edit"] is False
    assert stale_draft.json()["assessment"]["can_submit"] is False
    assert any(
        question["read_only"]
        for step in stale_draft.json()["template"]["steps"]
        for question in step["questions"]
        if question["key"] == "problem_statement"
    )

    stale_put = dev_client.put(
        f"{base_path}/{first_assessment_id}/answers/problem_statement",
        json={"value": "Tentative de mutation sur un brouillon obsolète."},
        headers=consultant_headers,
    )
    stale_submit = dev_client.post(
        f"{base_path}/{first_assessment_id}/submit",
        headers=consultant_headers,
    )
    assert stale_put.status_code == 409
    assert stale_submit.status_code == 409

    current_draft = dev_client.get(
        f"{base_path}/{second_assessment_id}",
        headers=consultant_headers,
    )
    assert current_draft.status_code == 200
    assert current_draft.json()["assessment"]["can_edit"] is True
    assert current_draft.json()["assessment"]["can_submit"] is True


def test_assessment_lookup_is_scoped_to_the_use_case_path(
    dev_client, seeded_lifecycle_data
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    other_use_case_id = seeded_lifecycle_data["other_use_case_a_id"]
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    mismatched_base_path = _wizard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=other_use_case_id,
    )

    created = _create_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        headers=consultant_headers,
    )
    assessment_id = created["assessment"]["id"]

    mismatched_get = dev_client.get(
        f"{mismatched_base_path}/{assessment_id}",
        headers=consultant_headers,
    )
    mismatched_put = dev_client.put(
        f"{mismatched_base_path}/{assessment_id}/answers/problem_statement",
        json={"value": "Should not resolve"},
        headers=consultant_headers,
    )
    assert mismatched_get.status_code == 404
    assert mismatched_put.status_code == 404


def test_wizard_cross_workspace_idor_is_blocked(dev_client, seeded_lifecycle_data) -> None:
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    created = _create_assessment(
        dev_client,
        workspace_id=seeded_lifecycle_data["workspace_a_id"],
        program_id=seeded_lifecycle_data["program_a_id"],
        use_case_id=seeded_lifecycle_data["use_case_a_id"],
        headers=consultant_headers,
    )
    assessment_id = created["assessment"]["id"]
    foreign_base_path = _wizard_base(
        workspace_id=seeded_lifecycle_data["workspace_b_id"],
        program_id=seeded_lifecycle_data["program_b_id"],
        use_case_id=seeded_lifecycle_data["use_case_b_id"],
    )

    assert (
        dev_client.get(f"{foreign_base_path}/current", headers=consultant_headers).status_code
        == 404
    )
    assert (
        dev_client.get(
            f"{foreign_base_path}/{assessment_id}",
            headers=consultant_headers,
        ).status_code
        == 404
    )
    assert (
        dev_client.post(
            f"{foreign_base_path}/{assessment_id}/validate-step/1",
            headers=consultant_headers,
        ).status_code
        == 404
    )


def test_hypothesis_sync_deletes_only_current_workspace_rows(
    dev_client, seeded_lifecycle_data
) -> None:
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    created = _create_assessment(
        dev_client,
        workspace_id=seeded_lifecycle_data["workspace_a_id"],
        program_id=seeded_lifecycle_data["program_a_id"],
        use_case_id=seeded_lifecycle_data["use_case_a_id"],
        headers=consultant_headers,
    )
    assessment_id = uuid.UUID(created["assessment"]["id"])

    with Session(get_engine()) as session:
        session.add(
            Hypothesis(
                workspace_id=seeded_lifecycle_data["workspace_b_id"],
                use_case_id=seeded_lifecycle_data["use_case_b_id"],
                assessment_version_id=assessment_id,
                statement="Foreign tenant hypothesis must survive local sync.",
                kind=HypothesisKind.RISK,
                status=HypothesisStatus.OPEN,
            )
        )
        session.commit()

    _put_answer(
        dev_client,
        workspace_id=seeded_lifecycle_data["workspace_a_id"],
        program_id=seeded_lifecycle_data["program_a_id"],
        use_case_id=seeded_lifecycle_data["use_case_a_id"],
        assessment_id=assessment_id,
        question_key="value_hypothesis",
        value="Local value hypothesis after sync.",
        headers=consultant_headers,
    )

    with Session(get_engine()) as session:
        surviving_foreign = session.exec(
            select(Hypothesis).where(
                Hypothesis.workspace_id == seeded_lifecycle_data["workspace_b_id"],
                Hypothesis.assessment_version_id == assessment_id,
            )
        ).all()
        local_hypotheses = session.exec(
            select(Hypothesis).where(
                Hypothesis.workspace_id == seeded_lifecycle_data["workspace_a_id"],
                Hypothesis.assessment_version_id == assessment_id,
            )
        ).all()

    assert [hypothesis.statement for hypothesis in surviving_foreign] == [
        "Foreign tenant hypothesis must survive local sync."
    ]
    assert [hypothesis.statement for hypothesis in local_hypotheses] == [
        "Local value hypothesis after sync."
    ]


def test_wizard_rejects_edge_values_and_unsupported_multiselect_entries(
    dev_client, seeded_lifecycle_data
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    headers = dev_headers("consultant-a", roles="Consultant")
    base_path = _wizard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    created = _create_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        headers=headers,
    )
    assessment_id = created["assessment"]["id"]

    invalid_money = dev_client.put(
        f"{base_path}/{assessment_id}/answers/hourly_cost",
        json={"value": -1},
        headers=headers,
    )
    invalid_scale = dev_client.put(
        f"{base_path}/{assessment_id}/answers/data_quality_score",
        json={"value": 6},
        headers=headers,
    )
    _put_answer(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=assessment_id,
        question_key="solution_pattern",
        value="ai_case_processing",
        headers=headers,
    )
    invalid_multiselect = dev_client.put(
        f"{base_path}/{assessment_id}/answers/case_processing_sensitive_flags",
        json={"value": ["personal", "unknown"]},
        headers=headers,
    )

    assert invalid_money.status_code == 422
    assert invalid_scale.status_code == 422
    assert invalid_multiselect.status_code == 422


def test_wizard_reports_misconfigured_schema_and_operator(
    dev_client, seeded_lifecycle_data
) -> None:
    headers = dev_headers("consultant-a", roles="Consultant")
    created = _create_assessment(
        dev_client,
        workspace_id=seeded_lifecycle_data["workspace_a_id"],
        program_id=seeded_lifecycle_data["program_a_id"],
        use_case_id=seeded_lifecycle_data["use_case_a_id"],
        headers=headers,
    )
    assessment_id = created["assessment"]["id"]
    base_path = _wizard_base(
        workspace_id=seeded_lifecycle_data["workspace_a_id"],
        program_id=seeded_lifecycle_data["program_a_id"],
        use_case_id=seeded_lifecycle_data["use_case_a_id"],
    )

    with Session(get_engine()) as session:
        question = session.exec(
            select(QuestionDefinition).where(QuestionDefinition.question_key == "problem_statement")
        ).one()
        question.validation_schema_json = {"type": "object"}
        session.add(question)
        session.commit()

    schema_response = dev_client.put(
        f"{base_path}/{assessment_id}/answers/problem_statement",
        json={"value": "Tentative avec schéma invalide."},
        headers=headers,
    )
    assert schema_response.status_code == 500

    with Session(get_engine()) as session:
        question = session.exec(
            select(QuestionDefinition).where(
                QuestionDefinition.question_key == "data_unavailable_reason"
            )
        ).one()
        question.validation_schema_json = {"type": "string", "min_length": 5, "max_length": 1500}
        question.conditional_rules_json = {
            "visible_if": [
                {
                    "question_key": "data_availability",
                    "operator": "bogus",
                    "value": "unavailable",
                }
            ]
        }
        session.add(question)
        session.commit()

    operator_response = dev_client.get(f"{base_path}/current", headers=headers)
    assert operator_response.status_code == 500


def test_wizard_mutations_are_audited(dev_client, seeded_lifecycle_data) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    consultant_headers = dev_headers("consultant-a", roles="Consultant")

    created = _create_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        headers=consultant_headers,
    )
    assessment_id = created["assessment"]["id"]
    _put_answer(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=assessment_id,
        question_key="problem_statement",
        value="Audit trail check for wizard.",
        headers=consultant_headers,
    )

    with Session(get_engine()) as session:
        actions = [
            action
            for action in session.exec(
                select(AuditEvent.action).order_by(AuditEvent.occurred_at.asc())
            ).all()
        ]
    assert "assessment.created" in actions
    assert "assessment.answer_upserted" in actions
