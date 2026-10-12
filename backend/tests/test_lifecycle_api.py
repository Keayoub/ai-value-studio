from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.audit.models import AuditEvent
from app.db.models.lifecycle import UseCase, UseCaseStatus
from app.db.session import get_engine
from sqlmodel import Session, select

from backend.tests.conftest import dev_headers


def _set_use_case_status(
    *,
    use_case_id: uuid.UUID,
    status: UseCaseStatus,
    owner_membership_id: uuid.UUID | None = None,
) -> None:
    with Session(get_engine()) as session:
        use_case = session.get(UseCase, use_case_id)
        assert use_case is not None
        use_case.status = status
        use_case.submitted_at = (
            datetime.now(UTC)
            if status
            in {
                UseCaseStatus.SUBMITTED,
                UseCaseStatus.APPROVED,
                UseCaseStatus.REJECTED,
                UseCaseStatus.CHANGES_REQUESTED,
            }
            else None
        )
        use_case.approved_at = datetime.now(UTC) if status == UseCaseStatus.APPROVED else None
        if owner_membership_id is not None:
            use_case.owner_membership_id = owner_membership_id
        session.add(use_case)
        session.commit()


def _list_audit_actions() -> list[str]:
    with Session(get_engine()) as session:
        return [
            event.action
            for event in session.exec(
                select(AuditEvent).order_by(AuditEvent.occurred_at.asc())
            ).all()
        ]


@pytest.mark.parametrize(
    ("subject_suffix", "roles", "expectation"),
    [
        (
            "admin-a",
            "WorkspaceAdmin",
            {
                "list_status": 200,
                "list_count": 1,
                "get_status": 200,
                "create_status": 201,
                "patch_status": 200,
                "transition_status": 200,
                "members_status": 200,
                "assign_status": 201,
            },
        ),
        (
            "consultant-a",
            "Consultant",
            {
                "list_status": 200,
                "list_count": 1,
                "get_status": 200,
                "create_status": 201,
                "patch_status": 200,
                "transition_status": 200,
                "members_status": 200,
                "assign_status": 201,
            },
        ),
        (
            "sponsor-a",
            "Sponsor",
            {
                "list_status": 200,
                "list_count": 1,
                "get_status": 200,
                "create_status": 403,
                "patch_status": 403,
                "transition_status": 403,
                "members_status": 403,
                "assign_status": 403,
            },
        ),
        (
            "contributor-a",
            "Contributor",
            {
                "list_status": 200,
                "list_count": 1,
                "get_status": 200,
                "create_status": 403,
                "patch_status": 403,
                "transition_status": 403,
                "members_status": 403,
                "assign_status": 403,
            },
        ),
    ],
)
def test_program_endpoint_role_matrix(
    dev_client,
    seeded_lifecycle_data,
    subject_suffix: str,
    roles: str,
    expectation: dict[str, int],
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    sponsor_membership_id = seeded_lifecycle_data["sponsor_a_membership_id"]
    extra_membership_id = seeded_lifecycle_data["extra_a_membership_id"]

    headers = dev_headers(subject_suffix, roles=roles)
    list_response = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs",
        headers=headers,
    )
    get_response = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}",
        headers=headers,
    )
    create_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs",
        json={
            "name": f"New Program {subject_suffix}",
            "strategic_objective": "Expand AI portfolio",
            "sponsor_membership_id": str(sponsor_membership_id),
        },
        headers=headers,
    )
    patch_response = dev_client.patch(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}",
        json={"strategic_objective": f"Updated by {subject_suffix}"},
        headers=headers,
    )
    transition_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/transition",
        json={"target_status": "Discovery"},
        headers=headers,
    )
    members_response = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/members",
        headers=headers,
    )
    assign_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/members",
        json={
            "membership_id": str(extra_membership_id),
            "assignment_role": "Contributor",
        },
        headers=headers,
    )

    assert list_response.status_code == expectation["list_status"]
    if list_response.status_code == 200:
        assert len(list_response.json()["items"]) == expectation["list_count"]
    assert get_response.status_code == expectation["get_status"]
    assert create_response.status_code == expectation["create_status"]
    assert patch_response.status_code == expectation["patch_status"]
    assert transition_response.status_code == expectation["transition_status"]
    assert members_response.status_code == expectation["members_status"]
    assert assign_response.status_code == expectation["assign_status"]


@pytest.mark.parametrize(
    ("subject_suffix", "roles", "expectation"),
    [
        (
            "admin-a",
            "WorkspaceAdmin",
            {
                "list_count": 2,
                "list_status": 200,
                "get_status": 200,
                "create_status": 201,
                "patch_status": 200,
                "transition_status": 200,
            },
        ),
        (
            "consultant-a",
            "Consultant",
            {
                "list_count": 2,
                "list_status": 200,
                "get_status": 200,
                "create_status": 201,
                "patch_status": 200,
                "transition_status": 200,
            },
        ),
        (
            "sponsor-a",
            "Sponsor",
            {
                "list_count": 2,
                "list_status": 200,
                "get_status": 200,
                "create_status": 403,
                "patch_status": 403,
                "transition_status": 403,
            },
        ),
        (
            "contributor-a",
            "Contributor",
            {
                "list_count": 1,
                "list_status": 200,
                "get_status": 200,
                "create_status": 403,
                "patch_status": 403,
                "transition_status": 403,
            },
        ),
    ],
)
def test_use_case_endpoint_role_matrix(
    dev_client,
    seeded_lifecycle_data,
    subject_suffix: str,
    roles: str,
    expectation: dict[str, int],
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    contributor_membership_id = seeded_lifecycle_data["contributor_a_membership_id"]

    headers = dev_headers(subject_suffix, roles=roles)
    list_response = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases",
        headers=headers,
    )
    get_response = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}",
        headers=headers,
    )
    create_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases",
        json={
            "title": f"Created by {subject_suffix}",
            "department": "Operations",
            "owner_membership_id": str(contributor_membership_id),
        },
        headers=headers,
    )
    patch_response = dev_client.patch(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}",
        json={"recommendation": f"Updated by {subject_suffix}"},
        headers=headers,
    )
    transition_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/transition",
        json={"target_status": "InProgress"},
        headers=headers,
    )

    assert list_response.status_code == expectation["list_status"]
    if list_response.status_code == 200:
        assert len(list_response.json()["items"]) == expectation["list_count"]
    assert get_response.status_code == expectation["get_status"]
    assert create_response.status_code == expectation["create_status"]
    assert patch_response.status_code == expectation["patch_status"]
    assert transition_response.status_code == expectation["transition_status"]


@pytest.mark.parametrize(
    (
        "subject_suffix",
        "roles",
        "use_case_key",
        "starting_status",
        "target_status",
        "expected_status",
    ),
    [
        (
            "admin-a",
            "WorkspaceAdmin",
            "use_case_a_id",
            UseCaseStatus.DRAFT,
            UseCaseStatus.IN_PROGRESS,
            200,
        ),
        (
            "consultant-a",
            "Consultant",
            "use_case_a_id",
            UseCaseStatus.DRAFT,
            UseCaseStatus.IN_PROGRESS,
            200,
        ),
        (
            "consultant-a",
            "Consultant",
            "use_case_a_id",
            UseCaseStatus.CHANGES_REQUESTED,
            UseCaseStatus.IN_PROGRESS,
            409,
        ),
        (
            "admin-a",
            "WorkspaceAdmin",
            "use_case_a_id",
            UseCaseStatus.SUBMITTED,
            UseCaseStatus.IN_PROGRESS,
            409,
        ),
        (
            "consultant-a",
            "Consultant",
            "use_case_a_id",
            UseCaseStatus.APPROVED,
            UseCaseStatus.IN_PROGRESS,
            409,
        ),
        (
            "consultant-a",
            "Consultant",
            "use_case_a_id",
            UseCaseStatus.SUBMITTED,
            UseCaseStatus.APPROVED,
            403,
        ),
        (
            "sponsor-a",
            "Sponsor",
            "use_case_a_id",
            UseCaseStatus.SUBMITTED,
            UseCaseStatus.APPROVED,
            403,
        ),
        (
            "sponsor-a",
            "Sponsor",
            "use_case_a_id",
            UseCaseStatus.SUBMITTED,
            UseCaseStatus.IN_PROGRESS,
            403,
        ),
        (
            "sponsor-unassigned-a",
            "Sponsor",
            "other_use_case_a_id",
            UseCaseStatus.SUBMITTED,
            UseCaseStatus.APPROVED,
            403,
        ),
        (
            "contributor-a",
            "Contributor",
            "use_case_a_id",
            UseCaseStatus.DRAFT,
            UseCaseStatus.IN_PROGRESS,
            403,
        ),
        (
            "contributor-a",
            "WorkspaceAdmin",
            "use_case_a_id",
            UseCaseStatus.DRAFT,
            UseCaseStatus.IN_PROGRESS,
            403,
        ),
        (
            "consultant-a",
            "Consultant",
            "use_case_a_id",
            UseCaseStatus.DRAFT,
            UseCaseStatus.SUBMITTED,
            403,
        ),
    ],
)
def test_use_case_transition_authorization_matrix(
    dev_client,
    seeded_lifecycle_data,
    subject_suffix: str,
    roles: str,
    use_case_key: str,
    starting_status: UseCaseStatus,
    target_status: UseCaseStatus,
    expected_status: int,
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data[use_case_key]
    if use_case_key == "other_use_case_a_id":
        _set_use_case_status(
            use_case_id=use_case_id,
            status=starting_status,
            owner_membership_id=seeded_lifecycle_data["sponsor_unassigned_a_membership_id"],
        )
    else:
        _set_use_case_status(use_case_id=use_case_id, status=starting_status)
    before_actions = _list_audit_actions()

    response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/transition",
        json={"target_status": target_status.value},
        headers=dev_headers(subject_suffix, roles=roles),
    )

    assert response.status_code == expected_status

    with Session(get_engine()) as session:
        use_case = session.get(UseCase, use_case_id)
        assert use_case is not None
        assert use_case.status == (target_status if expected_status == 200 else starting_status)

    after_actions = _list_audit_actions()
    assert len(after_actions) == len(before_actions) + (1 if expected_status == 200 else 0)
    if expected_status == 200:
        assert after_actions[-1] == "use_case.transitioned"
        body = response.json()
        assert body["status"] == target_status.value
        if target_status == UseCaseStatus.SUBMITTED:
            assert body["submitted_at"] is not None
            assert body["approved_at"] is None
        if target_status == UseCaseStatus.APPROVED:
            assert body["approved_at"] is not None
        if target_status in {UseCaseStatus.CHANGES_REQUESTED, UseCaseStatus.REJECTED}:
            assert body["approved_at"] is None


def test_use_case_write_rejects_server_derived_field_injection(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    contributor_membership_id = seeded_lifecycle_data["contributor_a_membership_id"]
    headers = dev_headers("consultant-a", roles="Consultant")
    injected_fields = {
        "category": "Injected",
        "priority_score": 4.5,
        "score_version": 2,
        "confidence_level": "High",
        "current_assessment_version": 3,
    }

    create_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases",
        json={
            "title": "Injected use case",
            "department": "Operations",
            "owner_membership_id": str(contributor_membership_id),
            "recommendation": "Automate",
            **injected_fields,
        },
        headers=headers,
    )
    patch_response = dev_client.patch(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}",
        json={"recommendation": "Updated", **injected_fields},
        headers=headers,
    )

    assert create_response.status_code == 422
    assert patch_response.status_code == 422


def test_use_case_response_preserves_read_only_scoring_fields(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    contributor_membership_id = seeded_lifecycle_data["contributor_a_membership_id"]

    response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases",
        json={
            "title": "Response fields",
            "department": "Operations",
            "owner_membership_id": str(contributor_membership_id),
            "recommendation": "Observe",
        },
        headers=dev_headers("consultant-a", roles="Consultant"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["category"] is None
    assert body["priority_score"] is None
    assert body["score_version"] is None
    assert body["confidence_level"] is None
    assert body["current_assessment_version"] is None


def test_lifecycle_cross_workspace_idor_is_blocked(dev_client, seeded_lifecycle_data) -> None:
    workspace_a_id = seeded_lifecycle_data["workspace_a_id"]
    workspace_b_id = seeded_lifecycle_data["workspace_b_id"]
    program_a_id = seeded_lifecycle_data["program_a_id"]
    program_b_id = seeded_lifecycle_data["program_b_id"]
    use_case_a_id = seeded_lifecycle_data["use_case_a_id"]
    use_case_b_id = seeded_lifecycle_data["use_case_b_id"]
    contributor_b_membership_id = seeded_lifecycle_data["contributor_b_membership_id"]

    headers = dev_headers("consultant-a", roles="Consultant")

    responses = [
        dev_client.get(
            f"/api/v1/workspaces/{workspace_a_id}/programs/{program_b_id}",
            headers=headers,
        ),
        dev_client.get(
            f"/api/v1/workspaces/{workspace_b_id}/programs/{program_b_id}",
            headers=headers,
        ),
        dev_client.post(
            f"/api/v1/workspaces/{workspace_a_id}/programs/{program_a_id}/members",
            json={
                "membership_id": str(contributor_b_membership_id),
                "assignment_role": "Contributor",
            },
            headers=headers,
        ),
        dev_client.post(
            f"/api/v1/workspaces/{workspace_a_id}/programs/{program_a_id}/use-cases",
            json={
                "title": "Cross workspace owner",
                "owner_membership_id": str(contributor_b_membership_id),
            },
            headers=headers,
        ),
        dev_client.patch(
            f"/api/v1/workspaces/{workspace_a_id}/programs/{program_a_id}/use-cases/{use_case_a_id}",
            json={"owner_membership_id": str(contributor_b_membership_id)},
            headers=headers,
        ),
        dev_client.get(
            f"/api/v1/workspaces/{workspace_a_id}/programs/{program_b_id}/use-cases/{use_case_b_id}",
            headers=headers,
        ),
        dev_client.post(
            f"/api/v1/workspaces/{workspace_a_id}/programs/{program_b_id}/use-cases/{use_case_b_id}/transition",
            json={"target_status": "Approved"},
            headers=headers,
        ),
    ]

    assert [response.status_code for response in responses] == [404, 404, 404, 404, 404, 404, 404]


def test_contributor_cannot_see_unowned_use_case(dev_client, seeded_lifecycle_data) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    other_use_case_id = seeded_lifecycle_data["other_use_case_a_id"]

    response = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{other_use_case_id}",
        headers=dev_headers("contributor-a", roles="Contributor"),
    )

    assert response.status_code == 404


def test_program_and_use_case_transitions_are_audited(dev_client, seeded_lifecycle_data) -> None:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    sponsor_headers = dev_headers("sponsor-a", roles="Sponsor")

    program_transition = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/transition",
        json={"target_status": "Discovery"},
        headers=consultant_headers,
    )
    invalid_program_transition = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/transition",
        json={"target_status": "Draft"},
        headers=consultant_headers,
    )
    first_use_case_transition = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/transition",
        json={"target_status": "InProgress"},
        headers=consultant_headers,
    )
    second_use_case_transition = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/transition",
        json={"target_status": "Submitted"},
        headers=consultant_headers,
    )
    third_use_case_transition = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/transition",
        json={"target_status": "Approved"},
        headers=sponsor_headers,
    )
    invalid_role_use_case_transition = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/transition",
        json={"target_status": "Rejected"},
        headers=consultant_headers,
    )

    assert program_transition.status_code == 200
    assert program_transition.json()["status"] == "Discovery"
    assert invalid_program_transition.status_code == 409
    assert first_use_case_transition.status_code == 200
    assert first_use_case_transition.json()["status"] == "InProgress"
    assert second_use_case_transition.status_code == 403
    assert third_use_case_transition.status_code == 403
    assert invalid_role_use_case_transition.status_code == 403

    assert _list_audit_actions() == [
        "program.transitioned",
        "use_case.transitioned",
    ]
