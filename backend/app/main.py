from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Literal

from app.api.v1.errors import AppError, install_error_handlers
from app.api.v1.router import api_router
from app.config import AuthMode, get_settings
from app.db.session import database_ready
from app.schemas.identity import DevIdentityRequest, DevIdentityResponse
from app.security.dev_auth import require_loopback_request
from app.wizard.loader import validate_baseline_template
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

logger = logging.getLogger(__name__)
READY_ERROR_DETAIL = "Service temporarily unavailable."


def create_app() -> FastAPI:
    settings = get_settings()
    validate_baseline_template()
    cors_allowed_headers = [
        "Authorization",
        "Content-Type",
        "X-Request-ID",
    ]
    if settings.auth_mode == AuthMode.DEV:
        cors_allowed_headers.extend(
            [
                "X-Dev-Identity",
                "X-Dev-Name",
                "X-Dev-Roles",
            ]
        )

    app = FastAPI(
        title="AI Value Studio API",
        version="0.2.0",
        description="Secure identity and workspace API foundation for AI Value Studio.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=cors_allowed_headers,
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    install_error_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, Literal["ok"]]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready(request: Request) -> dict[str, Literal["ok"]]:
        try:
            database_ready()
        except Exception as exc:
            logger.error(
                "Readiness check failed",
                extra={
                    "request_id": getattr(request.state, "request_id", None),
                    "path": request.url.path,
                    "exception_type": type(exc).__name__,
                },
            )
            raise AppError(
                status_code=503,
                title="Service Unavailable",
                detail=READY_ERROR_DETAIL,
            ) from exc
        return {"status": "ok"}

    if settings.auth_mode == AuthMode.DEV:

        @app.post("/api/v1/dev/identity", response_model=DevIdentityResponse, tags=["dev"])
        async def select_dev_identity(
            payload: DevIdentityRequest,
            request: Request,
        ) -> DevIdentityResponse:
            try:
                require_loopback_request(request)
            except ValueError as exc:
                raise AppError(status_code=403, title="Forbidden", detail=str(exc)) from exc
            subject = f"dev:{payload.subject_id}"
            return DevIdentityResponse(
                subject=subject,
                issuer="dev",
                tenant_id="dev",
                oid=payload.subject_id,
                display_name=payload.display_name,
                role=payload.role,
                headers={
                    "X-Dev-Identity": subject,
                    "X-Dev-Name": payload.display_name,
                    "X-Dev-Roles": payload.role.value,
                },
            )

    app.include_router(api_router)
    return app


app = create_app()
