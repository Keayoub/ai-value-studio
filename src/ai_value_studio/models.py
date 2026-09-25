from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

MAX_KICKSTART_FIELD_CHARS = 800


DEFAULT_WEIGHTS: Dict[str, float] = {
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

    def __post_init__(self) -> None:
        if not 1 <= self.value <= 5:
            raise ValueError(f"Score for {self.dimension} must be between 1 and 5")


@dataclass(slots=True)
class ValueInputs:
    annual_volume: float
    time_saved_hours: float
    hourly_cost: float
    error_reduction_rate: float
    average_error_cost: float
    revenue_capacity_value: float
    estimated_annual_cost: float


@dataclass(slots=True)
class AssessmentInput:
    use_case_name: str
    program_name: str
    scores: List[DimensionScore]
    value_inputs: ValueInputs
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
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
    key_risks: List[str]
    dependencies: List[str]
    kpis: List[str]


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
                    f"{field_name} exceeds {MAX_KICKSTART_FIELD_CHARS} characters; provide a short summary only"
                )


@dataclass(slots=True)
class LlmKickstartOutput:
    problem_statement: str
    ai_solution_proposal: str
    suggested_kpis: List[str]
    value_hypotheses: List[str]
    initial_risks: List[str]
    missing_information: List[str]
    ai_assisted: bool = True
