from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

MAX_KICKSTART_FIELD_CHARS = 800
VALUE_CALCULATION_VERSION = "s5-v1"
DEFAULT_CURRENCY = "EUR"
DEFAULT_DISCOUNT_RATE = 0.10

SCORE_DIMENSIONS: tuple[str, ...] = (
    "business_value",
    "current_friction",
    "data_feasibility",
    "technical_feasibility",
    "adoption_potential",
    "risk_governance",
)


DEFAULT_WEIGHTS: dict[str, float] = {
    "business_value": 0.25,
    "current_friction": 0.15,
    "data_feasibility": 0.15,
    "technical_feasibility": 0.15,
    "adoption_potential": 0.10,
    "risk_governance": 0.20,
}


@dataclass(slots=True)
class DimensionScore:
    dimension: str
    value: int
    justification: str
    confidence: str = "medium"
    source: str = ""
    is_manual_override: bool = False
    override_reason: str | None = None

    def __post_init__(self) -> None:
        if self.dimension not in SCORE_DIMENSIONS:
            raise ValueError(f"Unknown scoring dimension: {self.dimension}")
        if not 1 <= self.value <= 5:
            raise ValueError(f"Score for {self.dimension} must be between 1 and 5")
        if not self.justification.strip():
            raise ValueError(f"Justification for {self.dimension} cannot be empty")
        self.confidence = normalize_confidence(self.confidence)
        if self.source and not self.source.strip():
            raise ValueError(f"Source for {self.dimension} cannot be blank")
        if self.is_manual_override and not (self.override_reason or "").strip():
            raise ValueError(f"Manual override for {self.dimension} requires a reason")


@dataclass(slots=True)
class ValueInputs:
    annual_volume: float
    time_saved_hours: float
    hourly_cost: float
    error_reduction_rate: float
    average_error_cost: float
    revenue_capacity_value: float
    estimated_annual_cost: float
    time_to_impact_months: int = 0
    primary_kpi: str = ""
    kpi_target: str = ""
    confidence: str = "medium"
    currency: str = DEFAULT_CURRENCY
    discount_rate: float = DEFAULT_DISCOUNT_RATE

    def __post_init__(self) -> None:
        numeric_fields = {
            "annual_volume": self.annual_volume,
            "time_saved_hours": self.time_saved_hours,
            "hourly_cost": self.hourly_cost,
            "error_reduction_rate": self.error_reduction_rate,
            "average_error_cost": self.average_error_cost,
            "revenue_capacity_value": self.revenue_capacity_value,
            "estimated_annual_cost": self.estimated_annual_cost,
            "discount_rate": self.discount_rate,
        }
        for field_name, value in numeric_fields.items():
            if not math.isfinite(value):
                raise ValueError(f"{field_name} must be finite")
            if value < 0:
                raise ValueError(f"{field_name} must be greater than or equal to zero")
        if self.time_to_impact_months < 0:
            raise ValueError("time_to_impact_months must be greater than or equal to zero")
        if self.error_reduction_rate > 100:
            raise ValueError("error_reduction_rate must be less than or equal to 100")
        self.confidence = normalize_confidence(self.confidence)
        self.currency = self.currency.strip().upper() or DEFAULT_CURRENCY


@dataclass(slots=True)
class CategoryThresholds:
    quick_win_priority_min: float = 4.0
    quick_win_readiness_min: float = 3.8
    quick_win_governance_min: int = 3
    strategic_bet_priority_min: float = 4.0
    foundation_readiness_max: float = 3.0
    reject_priority_max: float = 2.8
    reject_governance_max: int = 2


@dataclass(slots=True)
class ScoreConfiguration:
    version: int = 1
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    thresholds: CategoryThresholds = field(default_factory=CategoryThresholds)

    def __post_init__(self) -> None:
        validate_weights(self.weights)


@dataclass(slots=True)
class ScenarioValue:
    name: str
    annual_time_value: float
    error_avoidance_value: float
    revenue_capacity_value: float
    gross_value: float
    net_annual_value: float
    npv_3y: float
    payback_months: float | None


@dataclass(slots=True)
class SensitivityRange:
    lever: str
    baseline_net_annual_value: float
    low_net_annual_value: float
    high_net_annual_value: float
    low_delta: float
    high_delta: float
    low_npv_3y: float
    high_npv_3y: float


@dataclass(slots=True)
class ValueAssessmentResult:
    calculation_version: str
    currency: str
    annual_time_value: float
    error_avoidance_value: float
    gross_value: float
    net_annual_value: float
    npv_3y: float
    payback_months: float | None
    scenarios: list[ScenarioValue]
    sensitivities: list[SensitivityRange]


@dataclass(slots=True)
class ScoringSignals:
    duration_minutes_per_occurrence: float = 0.0
    impact_type: str = ""
    supporting_evidence_present: bool = False
    sponsor_present: bool = False
    data_availability: str = ""
    data_quality_score: int | None = None
    pilot_accessibility: str = ""
    sensitive_data_flag: str = ""
    deployment_environment: str = ""
    effort_band: str = ""
    dependency_statement: str = ""
    support_owner_present: bool = False
    team_skills_present: bool = False
    training_needs_present: bool = False
    risk_profile: str = ""
    affected_person_decision: bool = False
    human_validation_required: str = ""
    audit_logging_required: bool = False
    access_model: str = ""
    data_boundary: str = ""
    value_confidence: str = "medium"


@dataclass(slots=True)
class ScorecardComputation:
    priority_score: float
    readiness_average: float
    category: str
    overall_confidence: str
    dimensions: list[DimensionScore]


@dataclass(slots=True)
class AssessmentInput:
    use_case_name: str
    program_name: str
    scores: list[DimensionScore]
    value_inputs: ValueInputs
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    scored_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class UseCaseProfile:
    title: str
    organization: str
    department: str
    owner: str
    problem_statement: str
    ai_solution: str
    required_human_validation: str
    key_risks: list[str]
    dependencies: list[str]
    kpis: list[str]


@dataclass(slots=True)
class LlmKickstartInput:
    strategic_objective: str
    target_process: str
    current_friction: str
    impacted_department: str
    critical_constraints: str

    def __post_init__(self) -> None:
        fields = {
            "strategic_objective": self.strategic_objective,
            "target_process": self.target_process,
            "current_friction": self.current_friction,
            "impacted_department": self.impacted_department,
            "critical_constraints": self.critical_constraints,
        }
        for field_name, value in fields.items():
            if len(value) > MAX_KICKSTART_FIELD_CHARS:
                raise ValueError(
                    f"{field_name} exceeds {MAX_KICKSTART_FIELD_CHARS} characters; "
                    "provide a short summary only"
                )


@dataclass(slots=True)
class LlmKickstartOutput:
    problem_statement: str
    ai_solution_proposal: str
    suggested_kpis: list[str]
    value_hypotheses: list[str]
    initial_risks: list[str]
    missing_information: list[str]
    ai_assisted: bool = True


def normalize_confidence(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"low", "medium", "high"}:
        raise ValueError("Confidence must be one of: low, medium, high")
    return normalized


def validate_weights(weights: dict[str, float]) -> None:
    weight_keys = tuple(weights)
    if set(weight_keys) != set(SCORE_DIMENSIONS):
        missing = sorted(set(SCORE_DIMENSIONS) - set(weight_keys))
        extra = sorted(set(weight_keys) - set(SCORE_DIMENSIONS))
        fragments: list[str] = []
        if missing:
            fragments.append(f"missing dimensions: {', '.join(missing)}")
        if extra:
            fragments.append(f"unexpected dimensions: {', '.join(extra)}")
        raise ValueError("Invalid score weights (" + "; ".join(fragments) + ")")

    total = sum(Decimal(str(weight)) for weight in weights.values())
    if total != Decimal("1.00"):
        raise ValueError("Score weights must total exactly 1.00")
    for dimension, weight in weights.items():
        if Decimal(str(weight)) <= 0:
            raise ValueError(f"Score weight for {dimension} must be greater than zero")


def validate_dimension_scores(scores: list[DimensionScore]) -> None:
    expected = set(SCORE_DIMENSIONS)
    seen: set[str] = set()
    duplicates: list[str] = []
    for score in scores:
        if score.dimension in seen and score.dimension not in duplicates:
            duplicates.append(score.dimension)
        seen.add(score.dimension)

    fragments: list[str] = []
    missing = sorted(expected - seen)
    unexpected = sorted(seen - expected)
    if missing:
        fragments.append(f"missing dimensions: {', '.join(missing)}")
    if unexpected:
        fragments.append(f"unexpected dimensions: {', '.join(unexpected)}")
    if duplicates:
        fragments.append(f"duplicate dimensions: {', '.join(sorted(duplicates))}")
    if len(scores) != len(SCORE_DIMENSIONS) and not duplicates and not missing and not unexpected:
        fragments.append(f"expected exactly {len(SCORE_DIMENSIONS)} scores, got {len(scores)}")
    if fragments:
        raise ValueError("Invalid dimension scores (" + "; ".join(fragments) + ")")
