from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class AuthMode(StrEnum):
    DEV = "dev"
    ENTRA = "entra"


class DocumentStorageDriver(StrEnum):
    LOCAL = "local"
    AZURE = "azure"


class LlmProviderKind(StrEnum):
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    FAKE = "fake"


def _split_csv(raw_value: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(raw_value, (list, tuple)):
        values = [str(item).strip() for item in raw_value if str(item).strip()]
    else:
        values = [item.strip() for item in raw_value.split(",") if item.strip()]
    if not values:
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    return values


def _is_loopback_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"}:
        return False
    return parsed.hostname in {"localhost", "127.0.0.1"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnv = AppEnv.LOCAL
    auth_mode: AuthMode = AuthMode.DEV
    debug: bool = True
    database_url: str = "sqlite:///./ai_value_studio.db"
    cors_allowed_origins_csv: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ALLOWED_ORIGINS",
    )

    entra_tenant_id: str | None = None
    entra_api_client_id: str | None = None
    entra_api_audience: str | None = None
    entra_required_scope: str = "access_as_user"
    entra_jwks_cache_ttl: int = 300
    entra_jwks_url: str | None = None

    dev_default_subject: str = "dev:workspace-admin"
    dev_default_name: str = "Local Workspace Admin"
    dev_user_role: str = "WorkspaceAdmin"
    dev_workspace_id: str | None = None
    document_storage_driver: DocumentStorageDriver = DocumentStorageDriver.LOCAL
    document_storage_path: str = Field(
        default="~/.local/state/ai-value-studio/documents",
        alias="DOCUMENT_STORAGE_PATH",
    )
    llm_provider: LlmProviderKind = LlmProviderKind.OPENAI
    llm_request_timeout_seconds: float = 20.0
    llm_rate_limit_requests: int = 6
    llm_rate_limit_window_seconds: int = 3600
    llm_circuit_breaker_failures: int = 3
    llm_circuit_breaker_open_seconds: int = 300
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_deployment_name: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-latest"

    @model_validator(mode="after")
    def validate_runtime_rules(self) -> Settings:
        if self.entra_jwks_cache_ttl < 1:
            raise ValueError("ENTRA_JWKS_CACHE_TTL must be greater than zero.")
        if any("*" in origin for origin in self.cors_allowed_origins):
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must contain exact origins; wildcard '*' is not allowed."
            )
        if self.auth_mode == AuthMode.DEV:
            if self.app_env not in {AppEnv.LOCAL, AppEnv.TEST}:
                raise ValueError("AUTH_MODE=dev is only allowed when APP_ENV is local or test.")
            if not self.debug:
                raise ValueError("AUTH_MODE=dev requires DEBUG=true.")
            if not (self.is_sqlite or self.is_test_database):
                raise ValueError("AUTH_MODE=dev requires SQLite or an explicit test database URL.")
            if not all(_is_loopback_origin(origin) for origin in self.cors_allowed_origins):
                raise ValueError("AUTH_MODE=dev requires loopback-only CORS origins.")

        if self.auth_mode == AuthMode.ENTRA:
            missing = [
                key
                for key, value in {
                    "ENTRA_TENANT_ID": self.entra_tenant_id,
                    "ENTRA_API_CLIENT_ID": self.entra_api_client_id,
                    "ENTRA_API_AUDIENCE": self.entra_api_audience,
                    "ENTRA_REQUIRED_SCOPE": self.entra_required_scope,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(f"AUTH_MODE=entra requires {', '.join(missing)}.")

        if self.document_storage_driver == DocumentStorageDriver.LOCAL:
            storage_path = self.document_storage_root
            repo_root = Path(__file__).resolve().parents[2]
            try:
                storage_path.relative_to(repo_root)
            except ValueError:
                pass
            else:
                raise ValueError(
                    "DOCUMENT_STORAGE_PATH must point outside the repository worktree."
                )

        if self.llm_request_timeout_seconds <= 0:
            raise ValueError("LLM_REQUEST_TIMEOUT_SECONDS must be greater than zero.")
        if self.llm_rate_limit_requests < 1:
            raise ValueError("LLM_RATE_LIMIT_REQUESTS must be greater than zero.")
        if self.llm_rate_limit_window_seconds < 1:
            raise ValueError("LLM_RATE_LIMIT_WINDOW_SECONDS must be greater than zero.")
        if self.llm_circuit_breaker_failures < 1:
            raise ValueError("LLM_CIRCUIT_BREAKER_FAILURES must be greater than zero.")
        if self.llm_circuit_breaker_open_seconds < 1:
            raise ValueError("LLM_CIRCUIT_BREAKER_OPEN_SECONDS must be greater than zero.")
        if self.llm_provider == LlmProviderKind.FAKE and self.app_env != AppEnv.TEST:
            raise ValueError("LLM_PROVIDER=fake is only allowed when APP_ENV is test.")

        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def cors_allowed_origins(self) -> list[str]:
        return _split_csv(self.cors_allowed_origins_csv)

    @property
    def is_test_database(self) -> bool:
        return "test" in self.database_url.lower()

    @property
    def entra_issuer(self) -> str:
        if not self.entra_tenant_id:
            raise RuntimeError("ENTRA_TENANT_ID is required to resolve the issuer.")
        return f"https://login.microsoftonline.com/{self.entra_tenant_id}/v2.0"

    @property
    def resolved_jwks_url(self) -> str:
        if self.entra_jwks_url:
            return self.entra_jwks_url
        if not self.entra_tenant_id:
            raise RuntimeError("ENTRA_TENANT_ID is required to resolve the JWKS URL.")
        return f"https://login.microsoftonline.com/{self.entra_tenant_id}/discovery/v2.0/keys"

    @property
    def document_storage_root(self) -> Path:
        return Path(self.document_storage_path).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
