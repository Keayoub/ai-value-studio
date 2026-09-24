from __future__ import annotations

from typing import Dict

from .models import AssessmentInput, ValueInputs


def compute_priority_score(assessment: AssessmentInput) -> float:
    """Compute weighted priority score on a 0-5 scale."""
    by_dimension = {s.dimension: s for s in assessment.scores}
    total = 0.0

    for dimension, weight in assessment.weights.items():
        if dimension not in by_dimension:
            raise ValueError(f"Missing score for dimension: {dimension}")
        total += by_dimension[dimension].value * weight

    return round(total, 3)


def classify_use_case(priority_score: float, risk_governance_score: int, readiness_average: float) -> str:
    """Classify use case according to studio portfolio buckets."""
    if priority_score >= 4.0 and readiness_average >= 3.8 and risk_governance_score >= 3:
        return "Quick Win"
    if priority_score >= 4.0 and readiness_average < 3.8:
        return "Strategic Bet"
    if readiness_average < 3.0:
        return "Foundation"
    if priority_score < 2.8 and risk_governance_score <= 2:
        return "Reject"
    return "Defer"


def compute_value_estimates(value_inputs: ValueInputs) -> Dict[str, float]:
    annual_time_value = value_inputs.annual_volume * value_inputs.time_saved_hours * value_inputs.hourly_cost
    error_avoidance = (
        value_inputs.annual_volume
        * value_inputs.error_reduction_rate
        * value_inputs.average_error_cost
    )
    gross = annual_time_value + error_avoidance + value_inputs.revenue_capacity_value
    net = gross - value_inputs.estimated_annual_cost

    return {
        "annual_time_value": round(annual_time_value, 2),
        "error_avoidance_value": round(error_avoidance, 2),
        "estimated_gross_value": round(gross, 2),
        "estimated_net_value": round(net, 2),
    }
