from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from app.api.v1.errors import AppError
from app.config import AuthMode, get_settings
from app.db.models.identity import IdentitySubject
from app.db.session import get_session, set_postgres_actor
from app.security.dev_auth import build_dev_identity, contains_dev_headers, require_loopback_request
from app.security.entra import JwksCache
from app.security.roles import ProductRole, parse_product_roles
from fastapi import Depends, Request
from jwt import InvalidTokenError
from sqlmodel import Session, select


@dataclass(slots=True)
class AuthContext:
    subject: str
    issuer: str
    tenant_id: str
    oid: str
    display_name: str | None
    email: str | None
    token_roles: set[ProductRole]
    identity_subject_id: uuid.UUID | None = None


@lru_cache(maxsize=4)
def _get_jwks_cache(jwks_url: str, ttl: int) -> JwksCache:
    return JwksCache(jwks_url=jwks_url, ttl_seconds=ttl)


def clear_jwks_cache() -> None:
    _get_jwks_cache.cache_clear()


def _get_authorization_token(request: Request) -> str:
    header_value = request.headers.get("Authorization")
    if not header_value:
        raise AppError(
            status_code=401,
            title="Unauthorized",
            detail="Missing Authorization header.",
        )
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError(
            status_code=401,
            title="Unauthorized",
            detail="Expected Bearer token.",
        )
    return token


def _validate_entra_token(token: str) -> AuthContext:
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise AppError(
            status_code=401,
            title="Unauthorized",
            detail="Malformed JWT header.",
        ) from exc

    kid = header.get("kid")
    alg = header.get("alg")
    if not kid:
        raise AppError(status_code=401, title="Unauthorized", detail="JWT kid is required.")
    if alg != "RS256":
        raise AppError(
            status_code=401,
            title="Unauthorized",
            detail="Only RS256 access tokens are accepted.",
        )

    jwks_cache = _get_jwks_cache(settings.resolved_jwks_url, settings.entra_jwks_cache_ttl)
    jwk = jwks_cache.get_key(kid)
    if jwk is None:
        raise AppError(status_code=401, title="Unauthorized", detail="Unknown signing key.")

    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
    try:
        payload = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            audience=settings.entra_api_audience,
            issuer=settings.entra_issuer,
            options={"require": ["exp", "nbf", "iss", "aud", "tid", "oid", "scp"]},
        )
    except InvalidTokenError as exc:
        raise AppError(
            status_code=401,
            title="Unauthorized",
            detail="Token validation failed.",
        ) from exc

    if payload.get("idtyp") == "id" or "nonce" in payload:
        raise AppError(status_code=401, title="Unauthorized", detail="ID tokens are not accepted.")
    if payload.get("tid") != settings.entra_tenant_id:
        raise AppError(status_code=401, title="Unauthorized", detail="Token tenant is not trusted.")

    scopes = {scope for scope in str(payload.get("scp", "")).split(" ") if scope}
    if settings.entra_required_scope not in scopes:
        raise AppError(status_code=403, title="Forbidden", detail="Required API scope is missing.")

    raw_roles = payload.get("roles")
    if not isinstance(raw_roles, list):
        raise AppError(
            status_code=403,
            title="Forbidden",
            detail="At least one known product role is required.",
        )
    roles = parse_product_roles(raw_roles)
    if not roles:
        raise AppError(
            status_code=403,
            title="Forbidden",
            detail="At least one known product role is required.",
        )

    return AuthContext(
        subject=f"{payload['iss']}|{payload['tid']}|{payload['oid']}",
        issuer=str(payload["iss"]),
        tenant_id=str(payload["tid"]),
        oid=str(payload["oid"]),
        display_name=payload.get("name"),
        email=payload.get("preferred_username"),
        token_roles=roles,
    )


def _find_identity_subject(session: Session, auth_context: AuthContext) -> IdentitySubject | None:
    statement = select(IdentitySubject).where(
        IdentitySubject.issuer == auth_context.issuer,
        IdentitySubject.tenant_id == auth_context.tenant_id,
        IdentitySubject.oid == auth_context.oid,
    )
    return session.exec(statement).first()


SessionDependency = Annotated[Session, Depends(get_session)]


def get_auth_context(
    request: Request,
    session: SessionDependency,
) -> AuthContext:
    settings = get_settings()

    if settings.auth_mode != AuthMode.DEV and contains_dev_headers(request):
        raise AppError(
            status_code=400,
            title="Bad Request",
            detail="X-Dev-* headers are rejected outside local dev mode.",
        )

    if settings.auth_mode == AuthMode.DEV:
        try:
            require_loopback_request(request)
        except ValueError as exc:
            raise AppError(status_code=403, title="Forbidden", detail=str(exc)) from exc
        try:
            dev_identity = build_dev_identity(request, settings)
        except ValueError as exc:
            raise AppError(status_code=400, title="Bad Request", detail=str(exc)) from exc
        auth_context = AuthContext(
            subject=dev_identity.subject,
            issuer=dev_identity.issuer,
            tenant_id=dev_identity.tenant_id,
            oid=dev_identity.oid,
            display_name=dev_identity.display_name,
            email=dev_identity.email,
            token_roles=dev_identity.roles,
        )
    else:
        auth_context = _validate_entra_token(_get_authorization_token(request))

    subject_row = _find_identity_subject(session, auth_context)
    if subject_row is not None:
        auth_context.identity_subject_id = subject_row.id
        set_postgres_actor(session, str(subject_row.id))
    return auth_context
