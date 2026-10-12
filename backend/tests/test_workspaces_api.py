from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from app.audit.models import AuditEvent
from app.audit.service import hash_audit_snapshot
from app.db.session import get_engine
from sqlmodel import Session, select

from backend.tests.conftest import dev_headers


def test_audit_snapshot_hashes_canonicalize_equivalent_utc_timestamps() -> None:
    aware_timestamp = datetime(2026, 10, 12, 6, 2, 40, 81000, tzinfo=UTC)
    naive_timestamp = aware_timestamp.replace(tzinfo=None)

    assert hash_audit_snapshot({"decided_at": aware_timestamp.isoformat()}) == hash_audit_snapshot(
        {"decided_at": naive_timestamp.isoformat()}
    )


def test_workspace_identity_views_are_scoped(dev_client, seeded_workspace_data) -> None:
    workspace_a_id = seeded_workspace_data["workspace_a_id"]
    workspace_b_id = seeded_workspace_data["workspace_b_id"]
    disabled_workspace_id = seeded_workspace_data["disabled_workspace_id"]

    me_response = dev_client.get("/api/v1/me", headers=dev_headers("actor"))
    list_response = dev_client.get("/api/v1/workspaces", headers=dev_headers("actor"))
    workspace_a_response = dev_client.get(
        f"/api/v1/workspaces/{workspace_a_id}", headers=dev_headers("actor")
    )
    workspace_b_response = dev_client.get(
        f"/api/v1/workspaces/{workspace_b_id}", headers=dev_headers("actor")
    )
    disabled_workspace_response = dev_client.get(
        f"/api/v1/workspaces/{disabled_workspace_id}", headers=dev_headers("actor")
    )
    members_a_response = dev_client.get(
        f"/api/v1/workspaces/{workspace_a_id}/members", headers=dev_headers("actor")
    )
    members_b_response = dev_client.get(
        f"/api/v1/workspaces/{workspace_b_id}/members", headers=dev_headers("actor")
    )

    assert me_response.status_code == 200
    assert me_response.json()["permitted_workspace_ids"] == [str(workspace_a_id)]
    assert all(
        membership["workspace_id"] != str(disabled_workspace_id)
        for membership in me_response.json()["memberships"]
    )
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["items"]] == [str(workspace_a_id)]
    assert workspace_a_response.status_code == 200
    assert workspace_b_response.status_code == 404
    assert disabled_workspace_response.status_code == 404
    assert members_a_response.status_code == 200
    assert all(
        item["workspace_id"] == str(workspace_a_id) for item in members_a_response.json()["items"]
    )
    assert members_b_response.status_code == 404


def test_cross_workspace_mutations_are_rejected(dev_client, seeded_workspace_data) -> None:
    workspace_a_id = seeded_workspace_data["workspace_a_id"]
    workspace_b_id = seeded_workspace_data["workspace_b_id"]
    target_b_membership_id = seeded_workspace_data["target_b_membership_id"]

    workspace_patch_response = dev_client.patch(
        f"/api/v1/workspaces/{workspace_b_id}",
        json={"name": "Not Allowed"},
        headers=dev_headers("actor"),
    )
    member_create_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_b_id}/members",
        json={
            "identity": {
                "issuer": "dev",
                "tenant_id": "dev",
                "oid": "new-user",
                "subject": "dev:new-user",
                "display_name": "New User",
                "email": "new-user@local.dev",
            },
            "role": "Contributor",
        },
        headers=dev_headers("actor"),
    )
    altered_member_response = dev_client.patch(
        f"/api/v1/workspaces/{workspace_a_id}/members/{target_b_membership_id}",
        json={"status": "disabled"},
        headers=dev_headers("actor"),
    )

    assert workspace_patch_response.status_code == 404
    assert member_create_response.status_code == 404
    assert altered_member_response.status_code == 404


def test_member_role_escalation_is_blocked(dev_client, seeded_workspace_data) -> None:
    workspace_a_id = seeded_workspace_data["workspace_a_id"]
    target_a_membership_id = seeded_workspace_data["target_a_membership_id"]

    create_admin_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_a_id}/members",
        json={
            "identity": {
                "issuer": "dev",
                "tenant_id": "dev",
                "oid": "candidate",
                "subject": "dev:candidate",
                "display_name": "Candidate",
                "email": "candidate@local.dev",
            },
            "role": "WorkspaceAdmin",
        },
        headers=dev_headers("actor", roles="Consultant"),
    )
    create_contributor_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_a_id}/members",
        json={
            "identity": {
                "issuer": "dev",
                "tenant_id": "dev",
                "oid": "candidate",
                "subject": "dev:candidate",
                "display_name": "Candidate",
                "email": "candidate@local.dev",
            },
            "role": "Contributor",
        },
        headers=dev_headers("actor", roles="Consultant"),
    )
    patch_response = dev_client.patch(
        f"/api/v1/workspaces/{workspace_a_id}/members/{target_a_membership_id}",
        json={"role": "WorkspaceAdmin"},
        headers=dev_headers("actor", roles="Consultant"),
    )

    assert create_admin_response.status_code == 403
    assert create_contributor_response.status_code == 403
    assert patch_response.status_code == 403


def test_consultant_created_workspace_keeps_membership_but_not_admin_permissions(
    dev_client,
) -> None:
    create_response = dev_client.post(
        "/api/v1/workspaces",
        json={
            "name": "Consultant Workspace",
            "default_language": "en",
            "confidentiality_policy": "internal-only",
        },
        headers=dev_headers("consultant-creator", roles="Consultant"),
    )

    assert create_response.status_code == 201
    workspace_id = create_response.json()["id"]
    assert create_response.json()["my_role"] == "WorkspaceAdmin"

    get_response = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}",
        headers=dev_headers("consultant-creator", roles="Consultant"),
    )
    patch_response = dev_client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"description": "Denied"},
        headers=dev_headers("consultant-creator", roles="Consultant"),
    )
    members_list_response = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers=dev_headers("consultant-creator", roles="Consultant"),
    )
    member_create_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={
            "identity": {
                "issuer": "dev",
                "tenant_id": "dev",
                "oid": "candidate",
                "subject": "dev:candidate",
                "display_name": "Candidate",
                "email": "candidate@local.dev",
            },
            "role": "Contributor",
        },
        headers=dev_headers("consultant-creator", roles="Consultant"),
    )

    assert get_response.status_code == 200
    assert patch_response.status_code == 403
    assert members_list_response.status_code == 403
    assert member_create_response.status_code == 403


def test_role_claim_downgrade_cannot_retain_workspace_admin_permissions(
    dev_client,
    seeded_workspace_data,
) -> None:
    workspace_a_id = seeded_workspace_data["workspace_a_id"]

    get_response = dev_client.get(
        f"/api/v1/workspaces/{workspace_a_id}",
        headers=dev_headers("actor", roles="Consultant"),
    )
    patch_response = dev_client.patch(
        f"/api/v1/workspaces/{workspace_a_id}",
        json={"description": "Denied"},
        headers=dev_headers("actor", roles="Consultant"),
    )
    members_list_response = dev_client.get(
        f"/api/v1/workspaces/{workspace_a_id}/members",
        headers=dev_headers("actor", roles="Consultant"),
    )

    assert get_response.status_code == 200
    assert patch_response.status_code == 403
    assert members_list_response.status_code == 403


def test_audit_events_record_each_mutation(dev_client) -> None:
    workspace_response = dev_client.post(
        "/api/v1/workspaces",
        json={
            "name": "Audited Workspace",
            "sector": "Financial Services",
            "country_region": "CA-QC",
            "size_band": "enterprise",
            "default_language": "fr-CA",
            "description": "Tracks mutations",
            "branding_json": {
                "primary_color": "#112233",
                "secondary_color": "#445566",
                "logo_url": "https://example.test/logo.png",
                "wordmark": "AVS",
            },
            "confidentiality_policy": "restricted",
        },
        headers=dev_headers("auditor"),
    )
    workspace_id = workspace_response.json()["id"]

    member_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={
            "identity": {
                "issuer": "dev",
                "tenant_id": "dev",
                "oid": "audited-member",
                "subject": "dev:audited-member",
                "display_name": "Audited Member",
                "email": "audited-member@local.dev",
            },
            "role": "Contributor",
        },
        headers=dev_headers("auditor"),
    )
    member_id = member_response.json()["membership_id"]

    workspace_patch_response = dev_client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"description": "Updated description"},
        headers=dev_headers("auditor"),
    )
    member_patch_response = dev_client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{member_id}",
        json={"status": "disabled"},
        headers=dev_headers("auditor"),
    )

    assert workspace_response.status_code == 201
    assert workspace_response.json()["sector"] == "Financial Services"
    assert workspace_response.json()["country_region"] == "CA-QC"
    assert workspace_response.json()["size_band"] == "enterprise"
    assert workspace_response.json()["default_language"] == "fr-CA"
    assert workspace_response.json()["branding_json"]["primary_color"] == "#112233"
    assert workspace_response.json()["confidentiality_policy"] == "restricted"
    assert member_response.status_code == 201
    assert workspace_patch_response.status_code == 200
    assert member_patch_response.status_code == 200

    with Session(get_engine()) as session:
        audit_events = list(
            session.exec(select(AuditEvent).order_by(AuditEvent.occurred_at.asc())).all()
        )

    assert [event.action for event in audit_events] == [
        "workspace.created",
        "workspace_member.created",
        "workspace.updated",
        "workspace_member.updated",
    ]
    assert [event.request_id for event in audit_events] == [
        workspace_response.headers["X-Request-ID"],
        member_response.headers["X-Request-ID"],
        workspace_patch_response.headers["X-Request-ID"],
        member_patch_response.headers["X-Request-ID"],
    ]
    assert [event.before_hash is not None for event in audit_events] == [False, False, True, True]
    assert [event.after_hash is not None for event in audit_events] == [True, True, True, True]
    assert audit_events[0].metadata_json == {"created_by_membership_role": "WorkspaceAdmin"}
    assert audit_events[1].metadata_json == {
        "membership_role": "Contributor",
        "membership_status": "active",
    }
    assert audit_events[2].metadata_json == {"changed_fields": ["description"]}
    assert audit_events[3].metadata_json == {"changed_fields": ["status"]}


def test_audit_events_store_deterministic_hashes_without_raw_payloads(
    dev_client,
) -> None:
    sensitive_description = "Client escalation for ceo@example.test"
    sensitive_email = "person@example.test"

    workspace_response = dev_client.post(
        "/api/v1/workspaces",
        json={
            "name": "Hashed Workspace",
            "default_language": "en",
            "description": sensitive_description,
            "confidentiality_policy": "internal-only",
        },
        headers=dev_headers("hash-auditor"),
    )
    workspace_id = workspace_response.json()["id"]
    expected_workspace_hash = hash_audit_snapshot(
        {"name": "Hashed Workspace", "status": "active"}
    )

    member_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={
            "identity": {
                "issuer": "dev",
                "tenant_id": "dev",
                "oid": "hashed-member",
                "subject": "dev:hashed-member",
                "display_name": "Hashed Member",
                "email": sensitive_email,
            },
            "role": "Contributor",
        },
        headers=dev_headers("hash-auditor"),
    )
    expected_member_hash = hash_audit_snapshot(
        {
            "role": "Contributor",
            "status": "active",
            "identity_subject_id": member_response.json()["identity"]["id"],
        }
    )
    assert workspace_response.status_code == 201
    assert member_response.status_code == 201

    with Session(get_engine()) as session:
        created_workspace_event = session.exec(
            select(AuditEvent).where(AuditEvent.action == "workspace.created")
        ).one()
        created_member_event = session.exec(
            select(AuditEvent).where(AuditEvent.action == "workspace_member.created")
        ).one()

    assert expected_workspace_hash == hashlib.sha256(
        json.dumps(
            {"name": "Hashed Workspace", "status": "active"},
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert created_workspace_event.after_hash == expected_workspace_hash
    assert created_member_event.after_hash == expected_member_hash
    assert "before_json" not in AuditEvent.model_fields
    assert "after_json" not in AuditEvent.model_fields
    workspace_payload = json.dumps(created_workspace_event.model_dump(mode="json"), sort_keys=True)
    member_payload = json.dumps(created_member_event.model_dump(mode="json"), sort_keys=True)
    assert sensitive_description not in workspace_payload
    assert sensitive_email not in member_payload
