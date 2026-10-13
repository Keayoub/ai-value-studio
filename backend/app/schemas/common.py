from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class CursorPaginationParams(BaseModel):
    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = None


T = TypeVar("T")


class CursorPageResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T]
    next_cursor: str | None = None
