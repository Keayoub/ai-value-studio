from __future__ import annotations

import logging

import pytest
from app.main import create_app
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_health_and_ready_endpoints(dev_client) -> None:
    health_response = dev_client.get("/health")
    ready_response = dev_client.get("/ready")

    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ok"}
    assert "X-Request-ID" in ready_response.headers


def test_cors_preflight_allows_configured_origin(dev_client) -> None:
    response = dev_client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization, Content-Type, X-Request-ID",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    assert "access-control-allow-credentials" not in response.headers


def test_cors_preflight_rejects_unknown_origin(dev_client) -> None:
    response = dev_client.options(
        "/health",
        headers={
            "Origin": "https://malicious.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_create_app_rejects_wildcard_cors(
    monkeypatch: pytest.MonkeyPatch, sqlite_db_url: str
) -> None:
    from backend.tests.conftest import configure_dev_env

    configure_dev_env(monkeypatch, sqlite_db_url, CORS_ALLOWED_ORIGINS="http://127.0.0.1:3000,*")

    with pytest.raises(ValidationError, match="wildcard"):
        create_app()


def test_ready_endpoint_redacts_sensitive_exception_details(
    caplog: pytest.LogCaptureFixture,
    dev_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sensitive_detail = "postgresql://user:super-secret@example.test/app"
    caplog.set_level(logging.ERROR)

    def broken_database_ready() -> bool:
        raise RuntimeError(sensitive_detail)

    monkeypatch.setattr("app.main.database_ready", broken_database_ready)

    response = dev_client.get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "Service temporarily unavailable."
    assert sensitive_detail not in response.text
    assert all(sensitive_detail not in record.getMessage() for record in caplog.records)


def test_unexpected_errors_redact_sensitive_exception_details(
    caplog: pytest.LogCaptureFixture,
    migrated_dev_app,
) -> None:
    sensitive_detail = "token=super-secret&email=person@example.test"
    caplog.set_level(logging.ERROR)

    @migrated_dev_app.get("/boom")
    async def boom() -> None:
        raise RuntimeError(sensitive_detail)

    with TestClient(migrated_dev_app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["detail"] == "An unexpected error occurred."
    assert sensitive_detail not in response.text
    assert all(sensitive_detail not in record.getMessage() for record in caplog.records)
