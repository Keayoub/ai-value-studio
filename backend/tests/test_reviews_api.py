from __future__ import annotations

import uuid

import pytest
from app.audit.models import AuditEvent
from app.audit.service import hash_audit_snapshot
from app.db.models.identity import IdentitySubject
from app.db.models.lifecycle import (
    Approval,
    AssessmentVersion,
    Program,
    ProgramAssignmentRole,
    Review,
    UseCase,
    UseCaseStatus,
)
from app.db.models.workspace import Workspace
from app.db.session import get_engine
from app.security.roles import ProductRole
from sqlmodel import Session, select

from backend.tests.conftest import (
    dev_headers,
    seed_identity,
    seed_membership,
    seed_program_member,
)
from backend.tests.test_wizard_api import _create_assessment, _fill_assessment


def _assessment_base(
    *,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
) -> str:
    return (
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}"
        f"/use-cases/{use_case_id}/assessments"
    )


def _submit_review_flow(
    dev_client,
    *,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
) -> tuple[str, str]:
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    assessment_id = _submit_assessment_flow(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        headers=consultant_headers,
    )
    review_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews",
        json={
            "recommendation": "Pilot",
            "summary": "Le périmètre pilote est prêt pour une validation sponsor.",
            "risks": ["Risque de qualité documentaire au démarrage."],
        },
        headers=consultant_headers,
    )
    assert review_response.status_code == 200
    return assessment_id, review_response.json()["review"]["id"]


def _submit_assessment_flow(
    dev_client,
    *,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
    headers: dict[str, str],
) -> str:
    assessment = _create_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        headers=headers,
    )
    assessment_id = assessment["assessment"]["id"]
    _fill_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=assessment_id,
        headers=headers,
    )
    base_path = _assessment_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    submit_response = dev_client.post(
        f"{base_path}/{assessment_id}/submit",
        headers=headers,
    )
    assert submit_response.status_code == 200
    return assessment_id


def _seed_visible_unassigned_consultant(
    *,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
) -> dict[str, str]:
    with Session(get_engine()) as session:
        workspace = session.get(Workspace, workspace_id)
        program = session.get(Program, program_id)
        use_case = session.get(UseCase, use_case_id)
        admin_identity = session.exec(
            select(IdentitySubject).where(IdentitySubject.subject == "dev:admin-a")
        ).one()
        assert workspace is not None
        assert program is not None
        assert use_case is not None
        extra_identity = seed_identity(
            session,
            suffix="consultant-unassigned-a",
            display_name="Consultant Unassigned A",
        )
        extra_membership = seed_membership(
            session,
            workspace=workspace,
            identity=extra_identity,
            role=ProductRole.CONSULTANT,
            created_by=admin_identity,
        )
        seed_program_member(
            session,
            workspace=workspace,
            program=program,
            membership=extra_membership,
            assignment_role=ProgramAssignmentRole.CONTRIBUTOR,
            created_by=admin_identity,
        )
        use_case.owner_membership_id = extra_membership.id
        session.add(use_case)
        session.commit()
    return dev_headers("consultant-unassigned-a", roles="Consultant")


def test_review_comment_approval_idempotency_and_audit(dev_client, seeded_lifecycle_data) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    assessment_id, review_id = _submit_review_flow(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    sponsor_headers = dev_headers("sponsor-a", roles="Sponsor")
    contributor_headers = dev_headers("contributor-a", roles="Contributor")
    comment_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/comments",
        json={"body": "Merci de préciser le risque principal pour le pilote."},
        headers=sponsor_headers,
    )
    assert comment_response.status_code == 200

    reply_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/comments",
        json={
            "body": "Le risque porte sur la complétude des pièces jointes.",
            "parent_comment_id": comment_response.json()["id"],
        },
        headers=contributor_headers,
    )
    assert reply_response.status_code == 200
    assert reply_response.json()["parent_comment_id"] == comment_response.json()["id"]

    approve_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/approve",
        json={"decision_reason": "Les garde-fous et le périmètre pilote sont suffisants."},
        headers={
            **sponsor_headers,
            "Idempotency-Key": "approve-1",
            "X-Request-ID": "approve-request-1",
        },
    )
    assert approve_response.status_code == 200
    body = approve_response.json()
    assert body["review"]["status"] == "Approved"
    assert body["review"]["approval"]["decision"] == "Approved"
    assert body["can_decide"] is False

    replay_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/approve",
        json={"decision_reason": "Les garde-fous et le périmètre pilote sont suffisants."},
        headers={
            **sponsor_headers,
            "Idempotency-Key": "approve-1",
            "X-Request-ID": "approve-request-1-replay",
        },
    )
    assert replay_response.status_code == 200
    assert replay_response.json() == body

    same_key_different_payload = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/reject",
        json={"decision_reason": "Conflit volontaire."},
        headers={
            **sponsor_headers,
            "Idempotency-Key": "approve-1",
            "X-Request-ID": "approve-request-1-conflict",
        },
    )
    different_key_same_payload = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/approve",
        json={"decision_reason": "Les garde-fous et le périmètre pilote sont suffisants."},
        headers={
            **sponsor_headers,
            "Idempotency-Key": "approve-2",
            "X-Request-ID": "approve-request-2-conflict",
        },
    )
    assert same_key_different_payload.status_code == 409
    assert different_key_same_payload.status_code == 409

    with Session(get_engine()) as session:
        use_case = session.get(UseCase, use_case_id)
        review = session.get(Review, uuid.UUID(review_id))
        approvals = session.exec(
            select(Approval).where(Approval.review_id == uuid.UUID(review_id))
        ).all()
        assessment = session.get(AssessmentVersion, uuid.UUID(assessment_id))
        sponsor_identity = session.exec(
            select(IdentitySubject).where(IdentitySubject.subject == "dev:sponsor-a")
        ).one()
        review_approved_audit = session.exec(
            select(AuditEvent).where(
                AuditEvent.request_id == "approve-request-1",
                AuditEvent.action == "review.approved",
            )
        ).one()
        use_case_approved_transition = session.exec(
            select(AuditEvent).where(
                AuditEvent.request_id == "approve-request-1",
                AuditEvent.action == "use_case.transitioned",
            )
        ).one()
        conflicting_request_audits = session.exec(
            select(AuditEvent).where(
                AuditEvent.request_id.in_(
                    ["approve-request-1-conflict", "approve-request-2-conflict"]
                )
            )
        ).all()
        assert use_case is not None
        assert use_case.status == UseCaseStatus.APPROVED
        assert use_case.approved_at is not None
        assert review is not None
        assert review.status.value == "Approved"
        assert review.decision_reason == "Les garde-fous et le périmètre pilote sont suffisants."
        assert len(approvals) == 1
        approval = approvals[0]
        assert approval.idempotency_key == "approve-1"
        assert approval.response_snapshot_json == body
        assert assessment is not None
        assert assessment.approved_at is not None
        assert review_approved_audit.actor_subject_id == sponsor_identity.id
        assert review_approved_audit.before_hash == hash_audit_snapshot(
            {
                "status": "Submitted",
                "decided_at": None,
                "decision_reason": None,
            }
        )
        assert review_approved_audit.after_hash == hash_audit_snapshot(
            {
                "status": "Approved",
                "decided_at": approval.decided_at.isoformat(),
                "decision_reason": "Les garde-fous et le périmètre pilote sont suffisants.",
            }
        )
        assert use_case_approved_transition.actor_subject_id == sponsor_identity.id
        assert use_case_approved_transition.before_hash == hash_audit_snapshot(
            {
                "status": UseCaseStatus.SUBMITTED,
                "submitted_at": assessment.submitted_at.isoformat(),
                "approved_at": None,
                "current_assessment_version": 1,
            }
        )
        assert use_case_approved_transition.after_hash == hash_audit_snapshot(
            {
                "status": UseCaseStatus.APPROVED,
                "submitted_at": assessment.submitted_at.isoformat(),
                "approved_at": assessment.approved_at.isoformat(),
                "current_assessment_version": 1,
            }
        )
        assert conflicting_request_audits == []
        audit_actions = [
            event.action
            for event in session.exec(
                select(AuditEvent).order_by(AuditEvent.occurred_at.asc())
            ).all()
        ]
    assert audit_actions.count("review.approved") == 1
    assert audit_actions.count("review.decision_replayed") == 1
    assert audit_actions[-6:] == [
        "review.created",
        "review.commented",
        "review.commented",
        "review.approved",
        "use_case.transitioned",
        "review.decision_replayed",
    ]


def test_review_submission_requires_assigned_consultant_and_rejects_workspace_admin(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    admin_headers = dev_headers("admin-a", roles="WorkspaceAdmin")
    unassigned_consultant_headers = _seed_visible_unassigned_consultant(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    _submit_assessment_flow(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        headers=consultant_headers,
    )

    admin_state = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/review",
        headers=admin_headers,
    )
    unassigned_consultant_state = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/review",
        headers=unassigned_consultant_headers,
    )
    admin_submit = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews",
        json={
            "recommendation": "Pilot",
            "summary": "Un administrateur ne doit pas soumettre la review.",
            "risks": [],
        },
        headers=admin_headers,
    )
    unassigned_consultant_submit = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews",
        json={
            "recommendation": "Pilot",
            "summary": "Un consultant non assigné ne doit pas soumettre la review.",
            "risks": [],
        },
        headers=unassigned_consultant_headers,
    )

    assert admin_state.status_code == 200
    assert admin_state.json()["can_submit_review"] is False
    assert unassigned_consultant_state.status_code == 200
    assert unassigned_consultant_state.json()["can_submit_review"] is False
    assert admin_submit.status_code == 409
    assert unassigned_consultant_submit.status_code == 409


def test_review_request_changes_creates_new_version_and_keeps_snapshots_immutable(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    sponsor_headers = dev_headers("sponsor-a", roles="Sponsor")
    assessment_id, review_id = _submit_review_flow(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    request_changes = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/request-changes",
        json={"decision_reason": "Préciser les garde-fous de qualité documentaire."},
        headers={**sponsor_headers, "Idempotency-Key": "changes-1"},
    )
    assert request_changes.status_code == 200
    assert request_changes.json()["review"]["status"] == "ChangesRequested"

    consultant_state = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/review",
        headers=consultant_headers,
    )
    assert consultant_state.status_code == 200
    assert consultant_state.json()["can_create_new_draft"] is True

    base_path = _assessment_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    mutate_submitted = dev_client.put(
        f"{base_path}/{assessment_id}/answers/problem_statement",
        json={"value": "Mutation interdite"},
        headers=consultant_headers,
    )
    assert mutate_submitted.status_code == 409

    new_draft = dev_client.post(
        _assessment_base(workspace_id=workspace_id, program_id=program_id, use_case_id=use_case_id),
        json={},
        headers=consultant_headers,
    )
    assert new_draft.status_code == 201
    assert new_draft.json()["assessment"]["version"] == 2
    assert new_draft.json()["assessment"]["status"] == "Draft"

    with Session(get_engine()) as session:
        submitted_assessment = session.get(AssessmentVersion, uuid.UUID(assessment_id))
        use_case = session.get(UseCase, use_case_id)
        assert submitted_assessment is not None
        assert submitted_assessment.submission_snapshot_json is not None
        assert submitted_assessment.approved_at is None
        assert use_case is not None
        assert use_case.status == UseCaseStatus.IN_PROGRESS
        assert use_case.submitted_at is None
        assert use_case.current_assessment_version == 2


def test_approved_assessment_requires_explicit_new_draft_version(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    sponsor_headers = dev_headers("sponsor-a", roles="Sponsor")
    assessment_id, review_id = _submit_review_flow(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    approve_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/approve",
        json={"decision_reason": "Le cadrage est validé pour cette version."},
        headers={**sponsor_headers, "Idempotency-Key": "approved-version-1"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["can_create_new_draft"] is False

    base_path = _assessment_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    implicit_new_draft = dev_client.post(
        base_path,
        json={},
        headers=consultant_headers,
    )
    assert implicit_new_draft.status_code == 409

    explicit_new_draft = dev_client.post(
        base_path,
        json={"force_new_version": True},
        headers={**consultant_headers, "X-Request-ID": "approved-reopen-request"},
    )
    assert explicit_new_draft.status_code == 201
    assert explicit_new_draft.json()["assessment"]["version"] == 2
    assert explicit_new_draft.json()["assessment"]["status"] == "Draft"

    with Session(get_engine()) as session:
        approved_assessment = session.get(AssessmentVersion, uuid.UUID(assessment_id))
        use_case = session.get(UseCase, use_case_id)
        consultant_identity = session.exec(
            select(IdentitySubject).where(IdentitySubject.subject == "dev:consultant-a")
        ).one()
        reopen_transition = session.exec(
            select(AuditEvent).where(
                AuditEvent.request_id == "approved-reopen-request",
                AuditEvent.action == "use_case.transitioned",
            )
        ).one()
        assert approved_assessment is not None
        assert approved_assessment.approved_at is not None
        assert approved_assessment.submission_snapshot_json is not None
        assert use_case is not None
        assert use_case.status == UseCaseStatus.IN_PROGRESS
        assert use_case.approved_at is None
        assert use_case.submitted_at is None
        assert use_case.current_assessment_version == 2
        assert reopen_transition.actor_subject_id == consultant_identity.id
        assert reopen_transition.before_hash == hash_audit_snapshot(
            {
                "status": UseCaseStatus.APPROVED,
                "submitted_at": approved_assessment.submitted_at.isoformat(),
                "approved_at": approved_assessment.approved_at.isoformat(),
                "current_assessment_version": 1,
            }
        )
        assert reopen_transition.after_hash == hash_audit_snapshot(
            {
                "status": UseCaseStatus.IN_PROGRESS,
                "submitted_at": None,
                "approved_at": None,
                "current_assessment_version": 2,
            }
        )


def test_review_replay_survives_follow_up_comment_and_new_draft(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    sponsor_headers = dev_headers("sponsor-a", roles="Sponsor")
    _, review_id = _submit_review_flow(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    request_changes = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/request-changes",
        json={"decision_reason": "Préciser les garde-fous documentaires avant validation."},
        headers={**sponsor_headers, "Idempotency-Key": "changes-1"},
    )
    assert request_changes.status_code == 200
    original_body = request_changes.json()

    comment_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/comments",
        json={"body": "Nous allons détailler les contrôles qualité dans la prochaine version."},
        headers=consultant_headers,
    )
    assert comment_response.status_code == 200

    new_draft = dev_client.post(
        _assessment_base(workspace_id=workspace_id, program_id=program_id, use_case_id=use_case_id),
        json={},
        headers=consultant_headers,
    )
    assert new_draft.status_code == 201
    assert new_draft.json()["assessment"]["version"] == 2

    replay_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/request-changes",
        json={"decision_reason": "Préciser les garde-fous documentaires avant validation."},
        headers={**sponsor_headers, "Idempotency-Key": "changes-1"},
    )
    assert replay_response.status_code == 200
    assert replay_response.json() == original_body


def test_review_state_targets_current_cycle_and_rejects_conflicting_idempotency_keys(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    sponsor_headers = dev_headers("sponsor-a", roles="Sponsor")
    _, first_review_id = _submit_review_flow(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    request_changes = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{first_review_id}/request-changes",
        json={"decision_reason": "Revoir les garde-fous documentaires."},
        headers={**sponsor_headers, "Idempotency-Key": "cycle-1"},
    )
    assert request_changes.status_code == 200

    new_draft = dev_client.post(
        _assessment_base(workspace_id=workspace_id, program_id=program_id, use_case_id=use_case_id),
        json={},
        headers=consultant_headers,
    )
    assert new_draft.status_code == 201
    assessment_v2_id = new_draft.json()["assessment"]["id"]
    assessment_base = _assessment_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    _fill_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=assessment_v2_id,
        headers=consultant_headers,
    )

    submit_v2 = dev_client.post(
        f"{assessment_base}/{assessment_v2_id}/submit",
        headers=consultant_headers,
    )
    assert submit_v2.status_code == 200

    second_review = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews",
        json={
            "recommendation": "Pilot",
            "summary": "La version 2 formalise les contrôles documentaires demandés.",
            "risks": ["Vérifier la montée en charge pilote."],
        },
        headers=consultant_headers,
    )
    assert second_review.status_code == 200
    second_review_body = second_review.json()
    second_review_id = second_review_body["review"]["id"]
    assert second_review_body["review"]["assessment_version"] == 2
    assert second_review_body["review_history"][0]["assessment_version"] == 1
    assert second_review_body["review_history"][0]["status"] == "ChangesRequested"

    sponsor_state = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/review",
        headers=sponsor_headers,
    )
    assert sponsor_state.status_code == 200
    assert sponsor_state.json()["review"]["assessment_version"] == 2
    assert sponsor_state.json()["review_history"][0]["assessment_version"] == 1
    assert sponsor_state.json()["can_decide"] is True

    conflicting_key = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{second_review_id}/approve",
        json={"decision_reason": "Cette clé est déjà utilisée sur un autre cycle."},
        headers={**sponsor_headers, "Idempotency-Key": "cycle-1"},
    )
    assert conflicting_key.status_code == 409


@pytest.mark.parametrize(
    ("first_route", "first_reason", "second_route", "second_reason"),
    [
        (
            "approve",
            "Validation du périmètre pilote.",
            "approve",
            "Validation du périmètre pilote.",
        ),
        ("approve", "Validation du périmètre pilote.", "reject", "Refus tardif interdit."),
        (
            "request-changes",
            "Préciser les garde-fous documentaires.",
            "approve",
            "Validation après décision terminale interdite.",
        ),
        (
            "reject",
            "Le dossier ne répond pas aux critères de cadrage.",
            "request-changes",
            "Nouvelle décision terminale interdite.",
        ),
    ],
)
def test_review_state_machine_conflict_matrix(
    dev_client,
    seeded_lifecycle_data,
    first_route: str,
    first_reason: str,
    second_route: str,
    second_reason: str,
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    _, review_id = _submit_review_flow(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    sponsor_headers = dev_headers("sponsor-a", roles="Sponsor")

    first_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/{first_route}",
        json={"decision_reason": first_reason},
        headers={**sponsor_headers, "Idempotency-Key": f"{first_route}-1"},
    )
    second_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/{second_route}",
        json={"decision_reason": second_reason},
        headers={**sponsor_headers, "Idempotency-Key": f"{second_route}-2"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409


def test_parent_comment_must_belong_to_current_review(dev_client, seeded_lifecycle_data) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    sponsor_headers = dev_headers("sponsor-a", roles="Sponsor")
    _, first_review_id = _submit_review_flow(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    first_comment = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/comments",
        json={"body": "Commentaire de la première review."},
        headers=sponsor_headers,
    )
    assert first_comment.status_code == 200
    request_changes = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{first_review_id}/request-changes",
        json={"decision_reason": "Reprendre la version."},
        headers={**sponsor_headers, "Idempotency-Key": "foreign-parent-1"},
    )
    assert request_changes.status_code == 200
    new_draft = dev_client.post(
        _assessment_base(
            workspace_id=workspace_id,
            program_id=program_id,
            use_case_id=use_case_id,
        ),
        json={},
        headers=consultant_headers,
    )
    assert new_draft.status_code == 201
    assessment_v2_id = new_draft.json()["assessment"]["id"]
    _fill_assessment(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        assessment_id=assessment_v2_id,
        headers=consultant_headers,
    )
    assessment_base = _assessment_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    submit_v2 = dev_client.post(
        f"{assessment_base}/{assessment_v2_id}/submit",
        headers=consultant_headers,
    )
    assert submit_v2.status_code == 200
    second_review = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews",
        json={
            "recommendation": "Pilot",
            "summary": "Version 2 soumise.",
            "risks": ["Toujours vérifier la complétude documentaire."],
        },
        headers=consultant_headers,
    )
    assert second_review.status_code == 200

    foreign_parent = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/comments",
        json={
            "body": "Tentative de rattachement au mauvais cycle.",
            "parent_comment_id": first_comment.json()["id"],
        },
        headers=consultant_headers,
    )
    assert foreign_parent.status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        (
            "get",
            "/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/review",
            None,
        ),
        (
            "get",
            "/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/comments",
            None,
        ),
        (
            "post",
            "/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/comments",
            {"body": "Cross-workspace comment"},
        ),
        ("get", "/api/v1/workspaces/{workspace_id}/review-inbox", None),
    ],
)
def test_review_cross_workspace_matrix(
    dev_client,
    seeded_lifecycle_data,
    method: str,
    path: str,
    body: dict[str, str] | None,
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    _, review_id = _submit_review_flow(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    formatted_path = path.format(
        workspace_id=seeded_lifecycle_data["workspace_b_id"],
        program_id=program_id,
        use_case_id=use_case_id,
        review_id=review_id,
    )
    request = getattr(dev_client, method)
    kwargs = {"headers": dev_headers("consultant-a", roles="Consultant")}
    if body is not None:
        kwargs["json"] = body
    response = request(formatted_path, **kwargs)
    assert response.status_code == 404


def test_review_authorization_cross_tenant_and_role_aware_inbox(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    _, review_id = _submit_review_flow(
        dev_client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    wrong_sponsor = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/approve",
        json={"decision_reason": "Je ne suis pas le sponsor assigné."},
        headers={
            **dev_headers("sponsor-unassigned-a", roles="Sponsor"),
            "Idempotency-Key": "wrong-sponsor",
        },
    )
    consultant_self_approve = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/approve",
        json={"decision_reason": "Un consultant ne peut pas s'auto-approuver."},
        headers={
            **dev_headers("consultant-a", roles="Consultant"),
            "Idempotency-Key": "consultant-self-approve",
        },
    )
    contributor_decision = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews/{review_id}/approve",
        json={"decision_reason": "Interdit"},
        headers={
            **dev_headers("contributor-a", roles="Contributor"),
            "Idempotency-Key": "contrib",
        },
    )
    cross_tenant_state = dev_client.get(
        f"/api/v1/workspaces/{seeded_lifecycle_data['workspace_b_id']}/programs/{program_id}/use-cases/{use_case_id}/review",
        headers=dev_headers("admin-b", roles="WorkspaceAdmin"),
    )
    sponsor_inbox = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/review-inbox",
        headers=dev_headers("sponsor-a", roles="Sponsor"),
    )
    contributor_inbox = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/review-inbox",
        headers=dev_headers("contributor-a", roles="Contributor"),
    )

    assert wrong_sponsor.status_code == 403
    assert consultant_self_approve.status_code == 403
    assert contributor_decision.status_code == 403
    assert cross_tenant_state.status_code == 404
    assert sponsor_inbox.status_code == 200
    assert sponsor_inbox.json()["items"][0]["review_id"] == review_id
    assert contributor_inbox.status_code == 200
    assert contributor_inbox.json()["items"] == []
