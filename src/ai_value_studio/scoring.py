from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .models import (
    VALUE_CALCULATION_VERSION,
    AssessmentInput,
    CategoryThresholds,
    DimensionScore,
    ScenarioValue,
    ScorecardComputation,
    ScoreConfiguration,
    ScoringSignals,
    SensitivityRange,
    ValueAssessmentResult,
    ValueInputs,
    normalize_confidence,
    validate_dimension_scores,
    validate_weights,
)

ROUND_THREE = Decimal("0.001")
ROUND_TWO = Decimal("0.01")
CONFIDENCE_VALUES = {"low": 1, "medium": 2, "high": 3}
BUSINESS_VALUE_THRESHOLDS = (
    (Decimal("500000"), 5),
    (Decimal("150000"), 4),
    (Decimal("50000"), 3),
    (Decimal("0.01"), 2),
)


def compute_priority_score(assessment: AssessmentInput) -> float:
    """Compute weighted priority score on a 0-5 scale."""
    validate_weights(assessment.weights)
    validate_dimension_scores(assessment.scores)
    by_dimension = {s.dimension: s for s in assessment.scores}
    total = 0.0

    for dimension, weight in assessment.weights.items():
        if dimension not in by_dimension:
            raise ValueError(f"Missing score for dimension: {dimension}")
        total += by_dimension[dimension].value * weight

    return round(total, 3)


def classify_use_case(
    priority_score: float,
    risk_governance_score: int,
    readiness_average: float,
    thresholds: CategoryThresholds | None = None,
    business_value_score: int | None = None,
) -> str:
    """Classify use case according to studio portfolio buckets."""
    limits = thresholds or CategoryThresholds()
    value_score = priority_score if business_value_score is None else business_value_score
    if (
        value_score >= limits.quick_win_priority_min
        and readiness_average >= limits.quick_win_readiness_min
        and risk_governance_score >= limits.quick_win_governance_min
    ):
        return "Quick Win"
    if readiness_average < limits.foundation_readiness_max:
        return "Foundation"
    if (
        priority_score < limits.reject_priority_max
        and risk_governance_score <= limits.reject_governance_max
    ):
        return "Reject"
    if (
        (
            value_score >= limits.quick_win_priority_min
            or priority_score >= limits.strategic_bet_priority_min
        )
        and readiness_average < limits.quick_win_readiness_min
    ):
        return "Strategic Bet"
    return "Defer"


def compute_value_estimates(value_inputs: ValueInputs) -> dict[str, float]:
    annual_time_value = (
        value_inputs.annual_volume * value_inputs.time_saved_hours * value_inputs.hourly_cost
    )
    error_avoidance = (
        value_inputs.annual_volume
        * _normalize_error_reduction_rate(value_inputs.error_reduction_rate)
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


def compute_readiness_average(scores: list[DimensionScore]) -> float:
    validate_dimension_scores(scores)
    by_dimension = {score.dimension: score for score in scores}
    readiness_dimensions = (
        "data_feasibility",
        "technical_feasibility",
        "adoption_potential",
    )
    missing = [dimension for dimension in readiness_dimensions if dimension not in by_dimension]
    if missing:
        raise ValueError(f"Missing score for readiness calculation: {', '.join(missing)}")
    average = sum(by_dimension[dimension].value for dimension in readiness_dimensions) / 3
    return float(_quantize(average, ROUND_THREE))


def compute_value_assessment(value_inputs: ValueInputs) -> ValueAssessmentResult:
    baseline = _compute_scenario("baseline", value_inputs, multiplier=Decimal("1.0"))
    conservative = _compute_scenario("conservative", value_inputs, multiplier=Decimal("0.8"))
    optimistic = _compute_scenario("optimistic", value_inputs, multiplier=Decimal("1.2"))

    sensitivities = [
        _compute_sensitivity(value_inputs, lever="time_saved_hours"),
        _compute_sensitivity(value_inputs, lever="error_reduction_rate"),
        _compute_sensitivity(value_inputs, lever="revenue_capacity_value"),
    ]
    return ValueAssessmentResult(
        calculation_version=VALUE_CALCULATION_VERSION,
        currency=value_inputs.currency,
        annual_time_value=baseline.annual_time_value,
        error_avoidance_value=baseline.error_avoidance_value,
        gross_value=baseline.gross_value,
        net_annual_value=baseline.net_annual_value,
        npv_3y=baseline.npv_3y,
        payback_months=baseline.payback_months,
        scenarios=[conservative, baseline, optimistic],
        sensitivities=sensitivities,
    )


def compute_scorecard(
    *,
    assessment: AssessmentInput,
    signals: ScoringSignals,
    configuration: ScoreConfiguration | None = None,
    manual_overrides: dict[str, tuple[int, str]] | None = None,
) -> ScorecardComputation:
    config = configuration or ScoreConfiguration()
    value_assessment = compute_value_assessment(assessment.value_inputs)
    dimensions = _deterministic_dimensions(
        value_inputs=assessment.value_inputs,
        value_assessment=value_assessment,
        signals=signals,
    )

    if manual_overrides:
        by_dimension = {dimension.dimension: dimension for dimension in dimensions}
        for dimension, override in manual_overrides.items():
            score_value, override_reason = override
            base = by_dimension.get(dimension)
            if base is None:
                raise ValueError(f"Unknown override dimension: {dimension}")
            by_dimension[dimension] = DimensionScore(
                dimension=dimension,
                value=score_value,
                justification=(
                    f"{base.justification} Override manuelle consultant: {override_reason.strip()}."
                ),
                confidence=base.confidence,
                source=base.source,
                is_manual_override=True,
                override_reason=override_reason.strip(),
            )
        dimensions = [by_dimension[dimension] for dimension in config.weights]

    scored_assessment = AssessmentInput(
        use_case_name=assessment.use_case_name,
        program_name=assessment.program_name,
        scores=dimensions,
        value_inputs=assessment.value_inputs,
        weights=config.weights,
        scored_at=assessment.scored_at,
    )
    priority_score = compute_priority_score(scored_assessment)
    readiness_average = compute_readiness_average(dimensions)
    business_value_score = next(
        score.value for score in dimensions if score.dimension == "business_value"
    )
    governance_score = next(
        score.value for score in dimensions if score.dimension == "risk_governance"
    )
    category = classify_use_case(
        priority_score=priority_score,
        risk_governance_score=governance_score,
        readiness_average=readiness_average,
        thresholds=config.thresholds,
        business_value_score=business_value_score,
    )
    return ScorecardComputation(
        priority_score=priority_score,
        readiness_average=readiness_average,
        category=category,
        overall_confidence=_overall_confidence(dimensions),
        dimensions=dimensions,
    )


def _deterministic_dimensions(
    *,
    value_inputs: ValueInputs,
    value_assessment: ValueAssessmentResult,
    signals: ScoringSignals,
) -> list[DimensionScore]:
    normalized_confidence = normalize_confidence(signals.value_confidence)
    dimensions = [
        _business_value_dimension(value_assessment, normalized_confidence),
        _current_friction_dimension(value_inputs, signals),
        _data_feasibility_dimension(signals),
        _technical_feasibility_dimension(signals),
        _adoption_dimension(signals),
        _risk_governance_dimension(signals),
    ]
    return dimensions


def _business_value_dimension(
    value_assessment: ValueAssessmentResult,
    confidence: str,
) -> DimensionScore:
    net_value = Decimal(str(value_assessment.net_annual_value))
    payback = value_assessment.payback_months
    score = 1
    for threshold, threshold_score in BUSINESS_VALUE_THRESHOLDS:
        if net_value >= threshold:
            score = threshold_score
            break
    if payback is not None and payback <= 12:
        score += 1
    elif payback is None or payback > 36:
        score -= 1
    if confidence == "low":
        score -= 1
    elif confidence == "high" and net_value > 0:
        score += 1
    final_score = _clamp_score(score)
    payback_label = (
        "non atteint sur 36 mois"
        if payback is None
        else f"{_format_decimal(payback, ROUND_TWO)} mois"
    )
    return DimensionScore(
        dimension="business_value",
        value=final_score,
        justification=(
            "Valeur nette annuelle "
            f"{_format_decimal(value_assessment.net_annual_value, ROUND_TWO)}, "
            f"NPV 3 ans {_format_decimal(value_assessment.npv_3y, ROUND_TWO)}, "
            f"payback {payback_label}."
        ),
        confidence=confidence,
        source="value_assessment",
    )


def _current_friction_dimension(
    value_inputs: ValueInputs,
    signals: ScoringSignals,
) -> DimensionScore:
    annual_manual_hours = Decimal(str(value_inputs.annual_volume)) * Decimal(
        str(signals.duration_minutes_per_occurrence)
    ) / Decimal("60")
    if annual_manual_hours >= Decimal("10000"):
        score = 5
    elif annual_manual_hours >= Decimal("5000"):
        score = 4
    elif annual_manual_hours >= Decimal("2000"):
        score = 3
    elif annual_manual_hours >= Decimal("500"):
        score = 2
    else:
        score = 1
    if signals.impact_type == "quantified":
        score += 1
    confidence = "high" if signals.supporting_evidence_present else "medium"
    return DimensionScore(
        dimension="current_friction",
        value=_clamp_score(score),
        justification=(
            "Environ "
            f"{_format_decimal(annual_manual_hours, ROUND_TWO)} heures annuelles sont mobilisées "
            "dans le processus courant."
        ),
        confidence=confidence,
        source="assessment.context+problem",
    )


def _data_feasibility_dimension(signals: ScoringSignals) -> DimensionScore:
    availability_scores = {"available": 5, "limited": 3, "unavailable": 1}
    accessibility_scores = {"ready": 5, "needs_work": 3, "blocked": 1}
    availability = availability_scores.get(signals.data_availability, 1)
    quality = signals.data_quality_score or 1
    accessibility = accessibility_scores.get(signals.pilot_accessibility, 1)
    penalty = {"none": 0, "personal": 0.25, "sensitive": 0.5}.get(
        signals.sensitive_data_flag, 0.5
    )
    average = (Decimal(availability) + Decimal(quality) + Decimal(accessibility)) / Decimal("3")
    score = _round_half_up_decimal(average - Decimal(str(penalty)))
    return DimensionScore(
        dimension="data_feasibility",
        value=_clamp_score(int(score)),
        justification=(
            "Disponibilité "
            f"{signals.data_availability or 'non précisée'}, qualité {quality}/5, "
            f"accessibilité pilote {signals.pilot_accessibility or 'non précisée'}."
        ),
        confidence="high" if signals.data_quality_score is not None else "medium",
        source="assessment.data",
    )


def _technical_feasibility_dimension(signals: ScoringSignals) -> DimensionScore:
    effort_scores = {"low": 5, "medium": 3, "high": 2}
    environment_scores = {"saas": 5, "customer_vpc": 4, "on_prem": 3}
    dependency_bonus = 1 if _looks_dependency_light(signals.dependency_statement) else 0
    average = (
        Decimal(effort_scores.get(signals.effort_band, 2))
        + Decimal(environment_scores.get(signals.deployment_environment, 3))
    ) / Decimal("2")
    score = int(_round_half_up_decimal(average)) + dependency_bonus
    return DimensionScore(
        dimension="technical_feasibility",
        value=_clamp_score(score),
        justification=(
            f"Bande d'effort {signals.effort_band or 'non précisée'}, environnement "
            f"{signals.deployment_environment or 'non précisé'}."
        ),
        confidence="medium" if signals.dependency_statement else "low",
        source="assessment.technical",
    )


def _adoption_dimension(signals: ScoringSignals) -> DimensionScore:
    factors = [
        5 if signals.sponsor_present else 2,
        5 if signals.support_owner_present else 1,
        4 if signals.team_skills_present else 2,
        3 if signals.training_needs_present else 4,
    ]
    average = sum(Decimal(value) for value in factors) / Decimal(str(len(factors)))
    confidence = "high" if signals.sponsor_present and signals.support_owner_present else "medium"
    return DimensionScore(
        dimension="adoption_potential",
        value=_clamp_score(int(_round_half_up_decimal(average))),
        justification=(
            "Sponsor "
            f"{'identifié' if signals.sponsor_present else 'absent'}, support "
            f"{'attribué' if signals.support_owner_present else 'à confirmer'}, compétences "
            f"{'documentées' if signals.team_skills_present else 'à consolider'}."
        ),
        confidence=confidence,
        source="assessment.technical+workspace.assignment",
    )


def _risk_governance_dimension(signals: ScoringSignals) -> DimensionScore:
    base_scores = {"Low": 5, "Medium": 4, "High": 2, "Critical": 1}
    score = base_scores.get(signals.risk_profile, 1)
    if signals.human_validation_required == "mandatory":
        score += 1
    if signals.audit_logging_required:
        score += 1
    if signals.access_model == "segregated":
        score += 1
    elif signals.access_model == "named_users":
        score -= 1
    if signals.affected_person_decision:
        score -= 1
    if signals.data_boundary == "approved_processor":
        score -= 1
    return DimensionScore(
        dimension="risk_governance",
        value=_clamp_score(score),
        justification=(
            f"Profil de risque {signals.risk_profile or 'non établi'}, validation humaine "
            f"{signals.human_validation_required or 'non précisée'}, modèle d'accès "
            f"{signals.access_model or 'non précisé'}."
        ),
        confidence="high" if signals.risk_profile else "medium",
        source="assessment.risk",
    )


def _compute_scenario(
    name: str,
    value_inputs: ValueInputs,
    *,
    multiplier: Decimal,
) -> ScenarioValue:
    annual_volume = Decimal(str(value_inputs.annual_volume))
    time_saved_hours = Decimal(str(value_inputs.time_saved_hours)) * multiplier
    hourly_cost = Decimal(str(value_inputs.hourly_cost))
    error_reduction_rate = Decimal(
        str(_normalize_error_reduction_rate(value_inputs.error_reduction_rate))
    )
    error_reduction_rate *= multiplier
    average_error_cost = Decimal(str(value_inputs.average_error_cost))
    revenue_capacity = Decimal(str(value_inputs.revenue_capacity_value)) * multiplier
    annual_cost = Decimal(str(value_inputs.estimated_annual_cost))
    annual_time_value = annual_volume * time_saved_hours * hourly_cost
    error_avoidance_value = annual_volume * error_reduction_rate * average_error_cost
    gross_value = annual_time_value + error_avoidance_value + revenue_capacity
    net_annual_value = gross_value - annual_cost
    npv_3y, payback_months = _discounted_npv_and_payback(
        gross_value=gross_value,
        annual_cost=annual_cost,
        time_to_impact_months=value_inputs.time_to_impact_months,
        annual_discount_rate=Decimal(str(value_inputs.discount_rate)),
    )
    return ScenarioValue(
        name=name,
        annual_time_value=float(_quantize(annual_time_value, ROUND_TWO)),
        error_avoidance_value=float(_quantize(error_avoidance_value, ROUND_TWO)),
        revenue_capacity_value=float(_quantize(revenue_capacity, ROUND_TWO)),
        gross_value=float(_quantize(gross_value, ROUND_TWO)),
        net_annual_value=float(_quantize(net_annual_value, ROUND_TWO)),
        npv_3y=float(_quantize(npv_3y, ROUND_TWO)),
        payback_months=float(_quantize(payback_months, ROUND_TWO))
        if payback_months is not None
        else None,
    )


def _compute_sensitivity(
    value_inputs: ValueInputs,
    *,
    lever: str,
) -> SensitivityRange:
    baseline = _compute_scenario("baseline", value_inputs, multiplier=Decimal("1.0"))
    lower = _compute_custom_sensitivity_scenario(value_inputs, lever, Decimal("0.8"))
    upper = _compute_custom_sensitivity_scenario(value_inputs, lever, Decimal("1.2"))
    return SensitivityRange(
        lever=lever,
        baseline_net_annual_value=baseline.net_annual_value,
        low_net_annual_value=lower.net_annual_value,
        high_net_annual_value=upper.net_annual_value,
        low_delta=float(
            _quantize(Decimal(str(lower.net_annual_value - baseline.net_annual_value)), ROUND_TWO)
        ),
        high_delta=float(
            _quantize(Decimal(str(upper.net_annual_value - baseline.net_annual_value)), ROUND_TWO)
        ),
        low_npv_3y=lower.npv_3y,
        high_npv_3y=upper.npv_3y,
    )


def _compute_custom_sensitivity_scenario(
    value_inputs: ValueInputs,
    lever: str,
    multiplier: Decimal,
) -> ScenarioValue:
    adjusted = ValueInputs(
        annual_volume=value_inputs.annual_volume,
        time_saved_hours=(
            float(Decimal(str(value_inputs.time_saved_hours)) * multiplier)
            if lever == "time_saved_hours"
            else value_inputs.time_saved_hours
        ),
        hourly_cost=value_inputs.hourly_cost,
        error_reduction_rate=(
            float(Decimal(str(value_inputs.error_reduction_rate)) * multiplier)
            if lever == "error_reduction_rate"
            else value_inputs.error_reduction_rate
        ),
        average_error_cost=value_inputs.average_error_cost,
        revenue_capacity_value=(
            float(Decimal(str(value_inputs.revenue_capacity_value)) * multiplier)
            if lever == "revenue_capacity_value"
            else value_inputs.revenue_capacity_value
        ),
        estimated_annual_cost=value_inputs.estimated_annual_cost,
        time_to_impact_months=value_inputs.time_to_impact_months,
        primary_kpi=value_inputs.primary_kpi,
        kpi_target=value_inputs.kpi_target,
        confidence=value_inputs.confidence,
        currency=value_inputs.currency,
        discount_rate=value_inputs.discount_rate,
    )
    return _compute_scenario(lever, adjusted, multiplier=Decimal("1.0"))


def _discounted_npv_and_payback(
    *,
    gross_value: Decimal,
    annual_cost: Decimal,
    time_to_impact_months: int,
    annual_discount_rate: Decimal,
) -> tuple[Decimal, Decimal | None]:
    monthly_discount_rate = (Decimal("1") + annual_discount_rate) ** (
        Decimal("1") / Decimal("12")
    ) - Decimal("1")
    monthly_cost = annual_cost / Decimal("12")
    monthly_benefit = gross_value / Decimal("12")
    cumulative = Decimal("0")
    payback: Decimal | None = None
    npv = Decimal("0")
    for month_index in range(1, 37):
        benefit = monthly_benefit if month_index > time_to_impact_months else Decimal("0")
        cashflow = benefit - monthly_cost
        discounted = cashflow / ((Decimal("1") + monthly_discount_rate) ** month_index)
        cumulative += discounted
        npv += discounted
        if payback is None and cumulative >= 0:
            payback = Decimal(month_index)
    return npv, payback


def _normalize_error_reduction_rate(value: float) -> float:
    return value / 100 if value > 1 else value


def _overall_confidence(scores: list[DimensionScore]) -> str:
    average = sum(CONFIDENCE_VALUES[score.confidence] for score in scores) / len(scores)
    if average >= 2.5:
        return "High"
    if average >= 1.75:
        return "Medium"
    return "Low"


def _looks_dependency_light(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"aucune", "aucun", "none", "n/a"} or "aucune dépendance" in normalized


def _clamp_score(value: int) -> int:
    return max(1, min(5, value))


def _format_decimal(value: float | Decimal, quantizer: Decimal) -> str:
    return str(_quantize(Decimal(str(value)), quantizer))


def _quantize(value: float | Decimal, quantizer: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP)


def _round_half_up_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
