from __future__ import annotations

import uuid
from datetime import datetime

from app.db.models.lifecycle import UseCaseStatus
from pydantic import BaseModel, Field


class PortfolioProgramFilterOption(BaseModel):
    id: uuid.UUID
    name: str
    count: int = Field(ge=0)


class PortfolioValueFilterOption(BaseModel):
    value: str
    label: str
    count: int = Field(ge=0)


class PortfolioAppliedFilters(BaseModel):
    program_id: uuid.UUID | None = None
    status: UseCaseStatus | None = None
    department: str | None = None
    risk_profile: str | None = None


class PortfolioAvailableFilters(BaseModel):
    programs: list[PortfolioProgramFilterOption]
    statuses: list[PortfolioValueFilterOption]
    departments: list[PortfolioValueFilterOption]
    risks: list[PortfolioValueFilterOption]


class PortfolioSummary(BaseModel):
    total_items: int = Field(ge=0)
    category_counts: dict[str, int]


class PortfolioItemResponse(BaseModel):
    workspace_id: uuid.UUID
    program_id: uuid.UUID
    use_case_id: uuid.UUID
    program_name: str
    use_case_title: str
    department: str | None = None
    status: UseCaseStatus
    recommendation: str | None = None
    category: str
    category_explanation_fr: str
    priority_score: float
    score_version: int = Field(ge=1)
    confidence_level: str
    business_value_score: int = Field(ge=1, le=5)
    readiness_average: float
    matrix_x: float
    matrix_y: float
    risk_profile: str
    risk_color: str
    risk_shape: str
    risk_pattern: str
    effort_band: str | None = None
    effort_label_fr: str | None = None
    currency: str
    net_annual_value: float
    updated_at: datetime


class PortfolioResponse(BaseModel):
    items: list[PortfolioItemResponse]
    summary: PortfolioSummary
    applied_filters: PortfolioAppliedFilters
    available_filters: PortfolioAvailableFilters
