from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from json import JSONDecodeError
from typing import Any
from urllib.error import URLError

import httpx
import jwt
import pytest
from app.config import get_settings
from app.main import create_app
from app.security.auth import AUTHENTICATION_UNAVAILABLE_DETAIL, INVALID_ACCESS_TOKEN_DETAIL
from app.security.dev_auth import build_dev_identity
from app.security.entra import JwksCache, JwksFetchError
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from backend.tests.conftest import configure_entra_env, dev_headers, run_upgrade


class DummyJwksCache:
    def __init__(self, jwk: dict[str, Any] | None) -> None:
        self.jwk = jwk

    def get_key(self, kid: str) -> dict[str, Any] | None:
        if self.jwk and self.jwk.get("kid") == kid:
            return self.jwk
        return None


@pytest.fixture
def rsa_material() -> dict[str, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk["kid"] = "test-kid"
    return {"private_key": private_key, "public_jwk": public_jwk}


def build_access_token(
    *,
    private_key,
    iss: str,
    aud: str,
    tid: str,
    headers: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
    algorithm: str = "RS256",
) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": iss,
        "aud": aud,
        "tid": tid,
        "oid": "user-123",
        "scp": "access_as_user",
        "roles": ["Consultant"],
        "nbf": now - timedelta(minutes=1),
        "exp": now + timedelta(minutes=5),
        "name": "Test User",
        "preferred_username": "test@example.com",
    }
    if overrides:
        claims.update(overrides)

    token_headers = {"kid": "test-kid"}
    if headers is not None:
        if headers.pop("omit_kid", False):
            token_headers.pop("kid", None)
        token_headers.update(headers)

    if algorithm == "none":
        return jwt.encode(claims, key=None, algorithm="none", headers=token_headers)
    if algorithm == "HS256":
        return jwt.encode(claims, key="secret", algorithm="HS256", headers=token_headers)
    return jwt.encode(claims, key=private_key, algorithm=algorithm, headers=token_headers)


def _make_entra_client(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
    rsa_material: dict[str, Any],
    *,
    patch_cache: bool = True,
) -> TestClient:
    configure_entra_env(monkeypatch, sqlite_db_url)
    run_upgrade(sqlite_db_url)
    if patch_cache:
        monkeypatch.setattr(
            "app.security.auth._get_jwks_cache",
            lambda _url, _ttl: DummyJwksCache(rsa_material["public_jwk"]),
        )
    return TestClient(create_app())


def test_jwks_cache_respects_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    class FakeResponse(BytesIO):
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.close()

    def fake_urlopen(url: str, timeout: int = 5) -> FakeResponse:
        assert url == "https://unit.test/jwks"
        assert timeout == 5
        calls["count"] += 1
        return FakeResponse(json.dumps({"keys": [{"kid": "abc", "kty": "RSA"}]}).encode("utf-8"))

    monkeypatch.setattr("app.security.entra.urlopen", fake_urlopen)
    cache = JwksCache(jwks_url="https://unit.test/jwks", ttl_seconds=60)

    assert cache.get_key("abc") == {"kid": "abc", "kty": "RSA"}
    assert cache.get_key("abc") == {"kid": "abc", "kty": "RSA"}
    assert calls["count"] == 1


def test_jwks_cache_throttles_repeated_fetch_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_urlopen(url: str, timeout: int = 5) -> BytesIO:
        assert url == "https://unit.test/jwks"
        assert timeout == 5
        calls["count"] += 1
        raise URLError("offline")

    monkeypatch.setattr("app.security.entra.urlopen", fake_urlopen)
    cache = JwksCache(jwks_url="https://unit.test/jwks", ttl_seconds=60, failure_retry_seconds=30)

    with pytest.raises(JwksFetchError):
        cache.get_key("abc")
    with pytest.raises(JwksFetchError):
        cache.get_key("abc")

    assert calls["count"] == 1


@pytest.mark.parametrize(
    ("claim_overrides", "algorithm", "headers", "expected_status"),
    [
        ({}, "RS256", {"kid": "test-kid"}, 200),
        ({"iss": "https://issuer.invalid/v2.0"}, "RS256", {"kid": "test-kid"}, 401),
        ({"aud": "api://wrong"}, "RS256", {"kid": "test-kid"}, 401),
        ({"tid": "wrong-tenant"}, "RS256", {"kid": "test-kid"}, 401),
        ({"exp": datetime.now(UTC) - timedelta(minutes=1)}, "RS256", {"kid": "test-kid"}, 401),
        ({"scp": "other_scope"}, "RS256", {"kid": "test-kid"}, 403),
        ({"roles": []}, "RS256", {"kid": "test-kid"}, 403),
        ({"nonce": "abc"}, "RS256", {"kid": "test-kid"}, 401),
        ({}, "HS256", {"kid": "test-kid"}, 401),
        ({}, "none", {"kid": "test-kid"}, 401),
        ({}, "RS256", {"omit_kid": True}, 401),
    ],
)
def test_entra_token_validation_matrix(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
    rsa_material: dict[str, Any],
    claim_overrides: dict[str, Any],
    algorithm: str,
    headers: dict[str, Any],
    expected_status: int,
) -> None:
    with _make_entra_client(monkeypatch, sqlite_db_url, rsa_material) as client:
        token = build_access_token(
            private_key=rsa_material["private_key"],
            iss="https://login.microsoftonline.com/tenant-123/v2.0",
            aud="api://client-123",
            tid="tenant-123",
            overrides=claim_overrides,
            headers=headers,
            algorithm=algorithm,
        )
        response = client.get("/api/v1/me", headers={"Authorization": "Bearer " + token})

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("label", "urlopen_factory"),
    [
        ("url-error", lambda: URLError("temporary dns failure")),
        ("timeout", lambda: TimeoutError("timed out")),
        ("malformed-jwks", lambda: BytesIO(b'{"keys":"unexpected"}')),
    ],
)
def test_entra_auth_returns_sanitized_503_for_jwks_failures(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
    rsa_material: dict[str, Any],
    label: str,
    urlopen_factory,
) -> None:
    class FakeResponse(BytesIO):
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.close()

    def fake_urlopen(url: str, timeout: int = 5):
        assert url == "https://unit.test/jwks"
        assert timeout == 5
        result = urlopen_factory()
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result.read())

    with _make_entra_client(monkeypatch, sqlite_db_url, rsa_material, patch_cache=False) as client:
        token = build_access_token(
            private_key=rsa_material["private_key"],
            iss="https://login.microsoftonline.com/tenant-123/v2.0",
            aud="api://client-123",
            tid="tenant-123",
        )
        monkeypatch.setattr("app.security.entra.urlopen", fake_urlopen)
        response = client.get("/api/v1/me", headers={"Authorization": "Bearer " + token})

    assert response.status_code == 503, label
    assert response.json()["title"] == "Service Unavailable"
    assert response.json()["detail"] == AUTHENTICATION_UNAVAILABLE_DETAIL
    assert "jwks" not in response.text.casefold()
    assert "unit.test" not in response.text


@pytest.mark.parametrize(
    ("label", "exception"),
    [
        ("url-error", URLError("temporary dns failure")),
        ("timeout", TimeoutError("timed out")),
        ("json-decode", JSONDecodeError("bad json", doc="{", pos=0)),
    ],
)
def test_entra_auth_returns_sanitized_503_when_cache_accessor_raises_directly(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
    rsa_material: dict[str, Any],
    label: str,
    exception: Exception,
) -> None:
    class ExplodingJwksCache:
        def get_key(self, kid: str) -> dict[str, Any] | None:
            assert kid == "test-kid"
            raise exception

    monkeypatch.setattr(
        "app.security.auth._get_jwks_cache",
        lambda _url, _ttl: ExplodingJwksCache(),
    )

    with _make_entra_client(monkeypatch, sqlite_db_url, rsa_material, patch_cache=False) as client:
        token = build_access_token(
            private_key=rsa_material["private_key"],
            iss="https://login.microsoftonline.com/tenant-123/v2.0",
            aud="api://client-123",
            tid="tenant-123",
        )
        response = client.get("/api/v1/me", headers={"Authorization": "Bearer " + token})

    assert response.status_code == 503, label
    assert response.json()["title"] == "Service Unavailable"
    assert response.json()["detail"] == AUTHENTICATION_UNAVAILABLE_DETAIL
    assert "dns" not in response.text.casefold()
    assert "timed out" not in response.text.casefold()
    assert "json" not in response.text.casefold()


def test_entra_auth_returns_sanitized_401_for_unknown_kid(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
    rsa_material: dict[str, Any],
) -> None:
    class FakeResponse(BytesIO):
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.close()

    def fake_urlopen(url: str, timeout: int = 5) -> FakeResponse:
        assert url == "https://unit.test/jwks"
        assert timeout == 5
        payload = {"keys": [{"kid": "other-kid", "kty": "RSA"}]}
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    with _make_entra_client(monkeypatch, sqlite_db_url, rsa_material, patch_cache=False) as client:
        token = build_access_token(
            private_key=rsa_material["private_key"],
            iss="https://login.microsoftonline.com/tenant-123/v2.0",
            aud="api://client-123",
            tid="tenant-123",
        )
        monkeypatch.setattr("app.security.entra.urlopen", fake_urlopen)
        response = client.get("/api/v1/me", headers={"Authorization": "Bearer " + token})

    assert response.status_code == 401
    assert response.json()["title"] == "Unauthorized"
    assert response.json()["detail"] == INVALID_ACCESS_TOKEN_DETAIL
    assert "kid" not in response.text.casefold()


def test_entra_auth_returns_sanitized_401_for_malformed_signing_key(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
    rsa_material: dict[str, Any],
) -> None:
    class FakeResponse(BytesIO):
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.close()

    def fake_urlopen(url: str, timeout: int = 5) -> FakeResponse:
        assert url == "https://unit.test/jwks"
        assert timeout == 5
        payload = {"keys": [{"kid": "test-kid", "kty": "RSA", "n": "bad", "e": "AQAB"}]}
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    with _make_entra_client(monkeypatch, sqlite_db_url, rsa_material, patch_cache=False) as client:
        token = build_access_token(
            private_key=rsa_material["private_key"],
            iss="https://login.microsoftonline.com/tenant-123/v2.0",
            aud="api://client-123",
            tid="tenant-123",
        )
        monkeypatch.setattr("app.security.entra.urlopen", fake_urlopen)
        response = client.get("/api/v1/me", headers={"Authorization": "Bearer " + token})

    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_ACCESS_TOKEN_DETAIL
    assert "rsa" not in response.text.casefold()


def test_entra_mode_rejects_dev_headers(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
    rsa_material: dict[str, Any],
) -> None:
    with _make_entra_client(monkeypatch, sqlite_db_url, rsa_material) as client:
        token = build_access_token(
            private_key=rsa_material["private_key"],
            iss="https://login.microsoftonline.com/tenant-123/v2.0",
            aud="api://client-123",
            tid="tenant-123",
        )
        response = client.get(
            "/api/v1/me",
            headers={
                "Authorization": "Bearer " + token,
                **dev_headers("actor"),
            },
        )

    assert response.status_code == 400
    assert "X-Dev-* headers are rejected" in response.json()["detail"]


def test_dev_identity_builder_requires_reserved_subject() -> None:
    from fastapi import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "client": ("127.0.0.1", 12345),
        "headers": [(b"x-dev-identity", b"not-dev"), (b"x-dev-roles", b"WorkspaceAdmin")],
    }
    request = Request(scope)

    with pytest.raises(ValueError, match="reserved dev:<id>"):
        build_dev_identity(request, get_settings())


@pytest.mark.asyncio
async def test_dev_mode_rejects_remote_client_headers(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
) -> None:
    from backend.tests.conftest import configure_dev_env

    configure_dev_env(monkeypatch, sqlite_db_url)
    run_upgrade(sqlite_db_url)
    transport = httpx.ASGITransport(app=create_app(), client=("10.0.0.8", 4321))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/me", headers=dev_headers("remote-actor"))

    assert response.status_code == 403
    assert "loopback clients" in response.json()["detail"]


@pytest.mark.asyncio
async def test_dev_identity_endpoint_rejects_remote_client(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
) -> None:
    from backend.tests.conftest import configure_dev_env

    configure_dev_env(monkeypatch, sqlite_db_url)
    run_upgrade(sqlite_db_url)
    transport = httpx.ASGITransport(app=create_app(), client=("10.0.0.8", 4321))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/dev/identity",
            json={
                "subject_id": "consultant",
                "display_name": "Local Consultant",
                "role": "Consultant",
            },
        )

    assert response.status_code == 403
    assert "loopback clients" in response.json()["detail"]


def test_dev_identity_endpoint_is_only_registered_in_dev(dev_client) -> None:
    response = dev_client.post(
        "/api/v1/dev/identity",
        json={"subject_id": "consultant", "display_name": "Local Consultant", "role": "Consultant"},
    )

    assert response.status_code == 200
    assert response.json()["subject"] == "dev:consultant"


def test_entra_mode_cors_does_not_advertise_dev_headers(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_db_url: str,
    rsa_material: dict[str, Any],
) -> None:
    with _make_entra_client(monkeypatch, sqlite_db_url, rsa_material) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization, X-Dev-Identity",
            },
        )

    assert response.status_code == 400
    assert "X-Dev-Identity" not in response.headers.get("access-control-allow-headers", "")
