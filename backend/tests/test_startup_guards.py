from __future__ import annotations

import os
import subprocess
import sys

import pytest
from app.main import create_app
from pydantic import ValidationError

from backend.tests.conftest import BACKEND_ROOT, REPO_ROOT, configure_dev_env, configure_entra_env


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"APP_ENV": "production"}, "AUTH_MODE=dev is only allowed"),
        ({"DEBUG": "false"}, "AUTH_MODE=dev requires DEBUG=true"),
        (
            {"DATABASE_URL": "postgresql+psycopg://db/prod"},
            "requires SQLite or an explicit test database",
        ),
        (
            {"CORS_ALLOWED_ORIGINS": "https://studio.example.com"},
            "requires loopback-only CORS origins",
        ),
    ],
)
def test_dev_mode_startup_guards(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
    overrides: dict[str, str],
    message: str,
) -> None:
    configure_dev_env(monkeypatch, sqlite_db_url, **overrides)

    with pytest.raises(ValidationError, match=message):
        create_app()


def test_entra_mode_requires_complete_configuration(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
) -> None:
    configure_entra_env(monkeypatch, sqlite_db_url, ENTRA_TENANT_ID="")

    with pytest.raises(ValidationError, match="AUTH_MODE=entra requires"):
        create_app()


@pytest.mark.parametrize("jwks_url", ["http://unit.test/jwks", "ftp://unit.test/jwks"])
@pytest.mark.parametrize("configure_env", [configure_dev_env, configure_entra_env])
def test_all_auth_modes_require_https_jwks_url(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
    configure_env,
    jwks_url: str,
) -> None:
    configure_env(monkeypatch, sqlite_db_url, ENTRA_JWKS_URL=jwks_url)

    with pytest.raises(ValidationError, match="ENTRA_JWKS_URL must use HTTPS"):
        create_app()


@pytest.mark.parametrize("app_env", ["local", "production"])
def test_fake_llm_provider_is_refused_outside_test_env(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
    app_env: str,
) -> None:
    configure = configure_dev_env if app_env == "local" else configure_entra_env
    configure(monkeypatch, sqlite_db_url, APP_ENV=app_env, LLM_PROVIDER="fake")

    with pytest.raises(
        ValidationError,
        match="LLM_PROVIDER=fake is only allowed when APP_ENV is test",
    ):
        create_app()


def test_subprocess_refuses_dev_mode_in_production(sqlite_db_url: str) -> None:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": f"{REPO_ROOT}:{BACKEND_ROOT}",
            "APP_ENV": "production",
            "AUTH_MODE": "dev",
            "DEBUG": "true",
            "DATABASE_URL": sqlite_db_url,
            "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:3000",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", "from app.main import app"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode != 0
    assert "AUTH_MODE=dev is only allowed" in (result.stderr + result.stdout)
