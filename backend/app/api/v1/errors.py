from __future__ import annotations

import logging
import uuid

from app.schemas.errors import ProblemDetail
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
UNEXPECTED_ERROR_DETAIL = "An unexpected error occurred."


class AppError(Exception):
    def __init__(
        self, *, status_code: int, title: str, detail: str, type_: str = "about:blank"
    ) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.type_ = type_
        super().__init__(detail)


def get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) else str(uuid.uuid4())


def problem_response(
    *,
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    type_: str = "about:blank",
) -> JSONResponse:
    payload = ProblemDetail(
        type=type_,
        title=title,
        status=status_code,
        detail=detail,
        instance=str(request.url.path),
        request_id=get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return problem_response(
            request=request,
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            type_=exc.type_,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return problem_response(
            request=request,
            status_code=422,
            title="Validation Error",
            detail=str(exc),
            type_="https://example.com/problems/validation-error",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled request exception",
            extra={
                "request_id": get_request_id(request),
                "method": request.method,
                "path": request.url.path,
                "exception_type": type(exc).__name__,
            },
        )
        return problem_response(
            request=request,
            status_code=500,
            title="Internal Server Error",
            detail=UNEXPECTED_ERROR_DETAIL,
        )
