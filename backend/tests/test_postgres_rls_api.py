from __future__ import annotations

from backend.tests.conftest import dev_headers


def test_postgres_rls_allows_real_api_flows_and_blocks_cross_tenant_access(
    postgres_dev_client,
) -> None:
    workspace_a_response = postgres_dev_client.post(
        "/api/v1/workspaces",
        json={
            "name": "Workspace A",
            "sector": "Public sector",
            "country_region": "CA-QC",
            "size_band": "enterprise",
            "default_language": "fr-CA",
            "description": "Workspace A description",
            "branding_json": {
                "primary_color": "#112233",
                "secondary_color": "#445566",
                "logo_url": "https://example.test/a-logo.png",
                "wordmark": "Workspace A",
            },
            "confidentiality_policy": "restricted",
        },
        headers=dev_headers("actor"),
    )
    workspace_b_response = postgres_dev_client.post(
        "/api/v1/workspaces",
        json={
            "name": "Workspace B",
            "sector": "Industry",
            "country_region": "US-NY",
            "size_band": "small",
            "default_language": "en",
            "description": "Workspace B description",
            "branding_json": {
                "primary_color": "#778899",
                "secondary_color": "#AABBCC",
            },
            "confidentiality_policy": "internal-only",
        },
        headers=dev_headers("outsider"),
    )

    assert workspace_a_response.status_code == 201
    assert workspace_b_response.status_code == 201

    workspace_a_id = workspace_a_response.json()["id"]
    workspace_b_id = workspace_b_response.json()["id"]

    actor_me_response = postgres_dev_client.get("/api/v1/me", headers=dev_headers("actor"))
    actor_list_response = postgres_dev_client.get(
        "/api/v1/workspaces",
        headers=dev_headers("actor"),
    )
    actor_get_workspace_response = postgres_dev_client.get(
        f"/api/v1/workspaces/{workspace_a_id}",
        headers=dev_headers("actor"),
    )
    actor_get_other_workspace_response = postgres_dev_client.get(
        f"/api/v1/workspaces/{workspace_b_id}",
        headers=dev_headers("actor"),
    )
    actor_members_response = postgres_dev_client.get(
        f"/api/v1/workspaces/{workspace_a_id}/members",
        headers=dev_headers("actor"),
    )
    actor_other_members_response = postgres_dev_client.get(
        f"/api/v1/workspaces/{workspace_b_id}/members",
        headers=dev_headers("actor"),
    )
    actor_add_member_response = postgres_dev_client.post(
        f"/api/v1/workspaces/{workspace_a_id}/members",
        json={
            "identity": {
                "issuer": "dev",
                "tenant_id": "dev",
                "oid": "member-a",
                "subject": "dev:member-a",
                "display_name": "Member A",
                "email": "member-a@local.dev",
            },
            "role": "Contributor",
        },
        headers=dev_headers("actor"),
    )
    actor_add_member_other_workspace_response = postgres_dev_client.post(
        f"/api/v1/workspaces/{workspace_b_id}/members",
        json={
            "identity": {
                "issuer": "dev",
                "tenant_id": "dev",
                "oid": "member-b",
                "subject": "dev:member-b",
                "display_name": "Member B",
                "email": "member-b@local.dev",
            },
            "role": "Contributor",
        },
        headers=dev_headers("actor"),
    )
    actor_patch_other_workspace_response = postgres_dev_client.patch(
        f"/api/v1/workspaces/{workspace_b_id}",
        json={"description": "not allowed"},
        headers=dev_headers("actor"),
    )
    actor_create_program_response = postgres_dev_client.post(
        f"/api/v1/workspaces/{workspace_a_id}/programs",
        json={"name": "Program A", "strategic_objective": "Assess the portfolio"},
        headers=dev_headers("actor"),
    )
    actor_create_program_other_workspace_response = postgres_dev_client.post(
        f"/api/v1/workspaces/{workspace_b_id}/programs",
        json={"name": "Program B"},
        headers=dev_headers("actor"),
    )

    assert actor_me_response.status_code == 200
    assert actor_me_response.json()["permitted_workspace_ids"] == [workspace_a_id]
    assert actor_list_response.status_code == 200
    assert [item["id"] for item in actor_list_response.json()["items"]] == [workspace_a_id]
    assert actor_get_workspace_response.status_code == 200
    assert actor_get_workspace_response.json()["confidentiality_policy"] == "restricted"
    assert actor_get_workspace_response.json()["branding_json"]["primary_color"] == "#112233"
    assert actor_get_other_workspace_response.status_code == 404
    assert actor_members_response.status_code == 200
    assert actor_other_members_response.status_code == 404
    assert actor_add_member_response.status_code == 201
    assert actor_add_member_other_workspace_response.status_code == 404
    assert actor_patch_other_workspace_response.status_code == 404
    assert actor_create_program_response.status_code == 201
    assert actor_create_program_other_workspace_response.status_code == 404

    membership_id = actor_add_member_response.json()["membership_id"]
    program_id = actor_create_program_response.json()["id"]
    actor_patch_member_response = postgres_dev_client.patch(
        f"/api/v1/workspaces/{workspace_a_id}/members/{membership_id}",
        json={"status": "disabled"},
        headers=dev_headers("actor"),
    )
    actor_get_program_response = postgres_dev_client.get(
        f"/api/v1/workspaces/{workspace_a_id}/programs/{program_id}",
        headers=dev_headers("actor"),
    )
    actor_get_other_program_response = postgres_dev_client.get(
        f"/api/v1/workspaces/{workspace_b_id}/programs/{program_id}",
        headers=dev_headers("outsider"),
    )
    actor_create_use_case_response = postgres_dev_client.post(
        f"/api/v1/workspaces/{workspace_a_id}/programs/{program_id}/use-cases",
        json={"title": "Use Case A"},
        headers=dev_headers("actor"),
    )

    assert actor_patch_member_response.status_code == 200
    assert actor_patch_member_response.json()["status"] == "disabled"
    assert actor_get_program_response.status_code == 200
    assert actor_get_other_program_response.status_code == 404
    assert actor_create_use_case_response.status_code == 201

    use_case_id = actor_create_use_case_response.json()["id"]
    actor_get_use_case_response = postgres_dev_client.get(
        f"/api/v1/workspaces/{workspace_a_id}/programs/{program_id}/use-cases/{use_case_id}",
        headers=dev_headers("actor"),
    )
    actor_create_assessment_response = postgres_dev_client.post(
        f"/api/v1/workspaces/{workspace_a_id}/programs/{program_id}/use-cases/{use_case_id}/assessments",
        json={},
        headers=dev_headers("actor"),
    )
    actor_get_scorecards_response = postgres_dev_client.get(
        f"/api/v1/workspaces/{workspace_a_id}/programs/{program_id}/use-cases/{use_case_id}/scorecards",
        headers=dev_headers("actor"),
    )
    actor_transition_use_case_response = postgres_dev_client.post(
        f"/api/v1/workspaces/{workspace_a_id}/programs/{program_id}/use-cases/{use_case_id}/transition",
        json={"target_status": "InProgress"},
        headers=dev_headers("actor"),
    )
    outsider_get_use_case_response = postgres_dev_client.get(
        f"/api/v1/workspaces/{workspace_b_id}/programs/{program_id}/use-cases/{use_case_id}",
        headers=dev_headers("outsider"),
    )
    outsider_get_scorecards_response = postgres_dev_client.get(
        f"/api/v1/workspaces/{workspace_b_id}/programs/{program_id}/use-cases/{use_case_id}/scorecards",
        headers=dev_headers("outsider"),
    )

    assert actor_get_use_case_response.status_code == 200
    assert actor_create_assessment_response.status_code == 201
    assert actor_get_scorecards_response.status_code == 200
    assert actor_get_scorecards_response.json()["score_configuration"]["weights"][
        "business_value"
    ] == 0.25
    assert actor_transition_use_case_response.status_code == 200
    assert actor_transition_use_case_response.json()["status"] == "InProgress"
    assert outsider_get_use_case_response.status_code == 404
    assert outsider_get_scorecards_response.status_code == 404
