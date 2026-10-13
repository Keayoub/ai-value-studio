from __future__ import annotations

from pydantic import BaseModel


class ProblemDetail(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    request_id: str
