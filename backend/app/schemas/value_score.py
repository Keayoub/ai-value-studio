from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Any

from app.db.models.lifecycle import ScoreDimension
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ValueAssessmentUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annual_volume: float = Field(ge=0, le=1000000000, allow_inf_nan=False)
    time_saved_hours: float = Field(ge=0, le=100000, allow_inf_nan=False)
    hourly_cost: float = Field(ge=0, le=1000000, allow_inf_nan=False)
    error_reduction_rate: float = Field(ge=0, le=100, allow_inf_nan=False)
    average_error_cost: float = Field(ge=0, le=100000000, allow_inf_nan=False)
    revenue_capacity_value: float = Field(ge=0, le=1000000000, allow_inf_nan=False)
    estimated_annual_cost: float = Field(ge=0, le=1000000000, allow_inf_nan=False)
    time_to_impact_months: int = Field(default=0, ge=0, le=120)
    primary_kpi: str = Field(min_length=1, max_length=255)
    kpi_target: str = Field(min_length=1, max_length=255)
    confidence: str = Field(min_length=1, max_length=16)
    currency: str = Field(min_length=3, max_length=3, default="EUR")

    @field_validator(
        "annual_volume",
        "time_saved_hours",
        "hourly_cost",
        "error_reduction_rate",
        "average_error_cost",
        "revenue_capacity_value",
        "estimated_annual_cost",
    )
    @classmethod
    def validate_finite_numbers(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Value must be finite.")
        return value


class ScorecardOverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: ScoreDimension
    score: int = Field(ge=1, le=5)
    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Override reason cannot be blank.")
        return value


class ScenarioValueResponse(BaseModel):
    name: str
    annual_time_value: float
    error_avoidance_value: float
    revenue_capacity_value: float
    gross_value: float
    net_annual_value: float
    npv_3y: float
    payback_months: float | None = None


class SensitivityRangeResponse(BaseModel):
    lever: str
    baseline_net_annual_value: float
    low_net_annual_value: float
    high_net_annual_value: float
    low_delta: float
    high_delta: float
    low_npv_3y: float
    high_npv_3y: float


class ValueAssessmentResponse(BaseModel):
    id: uuid.UUID | None = None
    workspace_id: uuid.UUID
    use_case_id: uuid.UUID
    assessment_version_id: uuid.UUID
    persisted: bool
    annual_volume: float
    time_saved_hours: float
    hourly_cost: float
    error_reduction_rate: float
    average_error_cost: float
    revenue_capacity_value: float
    estimated_annual_cost: float
    time_to_impact_months: int
    primary_kpi: str
    kpi_target: str
    confidence: str
    currency: str
    calculation_version: str
    annual_time_value: float
    error_avoidance_value: float
    gross_value: float
    net_annual_value: float
    npv_3y: float
    payback_months: float | None = None
    scenarios: list[ScenarioValueResponse]
    sensitivities: list[SensitivityRangeResponse]
    input_snapshot: dict[str, Any]
    source_snapshot: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScoreConfigurationResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    version: int
    is_active: bool
    weights: dict[str, float]
    thresholds: dict[str, float | int]
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_weights(self) -> ScoreConfigurationResponse:
        if round(sum(self.weights.values()), 6) != 1:
            raise ValueError("Weights must total exactly 1.00")
        return self


class DimensionScoreResponse(BaseModel):
    id: uuid.UUID
    dimension: ScoreDimension
    weight: float
    score: int
    source: str
    justification: str
    confidence: str
    is_manual_override: bool
    override_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class ScorecardVersionResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    use_case_id: uuid.UUID
    assessment_version_id: uuid.UUID
    value_assessment_id: uuid.UUID
    score_configuration_version_id: uuid.UUID
    version: int
    priority_score: float
    readiness_average: float
    category: str
    risk_profile: str
    confidence_level: str
    calculation_version: str
    manual_override: bool
    override_reason: str | None = None
    input_snapshot: dict[str, Any]
    formula_snapshot: dict[str, Any]
    dimensions: list[DimensionScoreResponse]
    created_by_subject_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class UseCaseScorecardResponse(BaseModel):
    value_assessment: ValueAssessmentResponse
    score_configuration: ScoreConfigurationResponse
    current_scorecard: ScorecardVersionResponse | None = None
    history: list[ScorecardVersionResponse] = Field(default_factory=list)
    read_only: bool
    can_override: bool
