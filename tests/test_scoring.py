import unittest
from dataclasses import asdict

from ai_value_studio.models import (
    VALUE_CALCULATION_VERSION,
    AssessmentInput,
    DimensionScore,
    ScoreConfiguration,
    ScoringSignals,
    ValueInputs,
)
from ai_value_studio.scoring import (
    classify_use_case,
    compute_priority_score,
    compute_readiness_average,
    compute_scorecard,
    compute_value_assessment,
    compute_value_estimates,
)


class ScoringTests(unittest.TestCase):
    def _value_inputs(self, **overrides: float | int) -> ValueInputs:
        inputs = {
            "annual_volume": 12,
            "time_saved_hours": 2,
            "hourly_cost": 10,
            "error_reduction_rate": 20,
            "average_error_cost": 5,
            "revenue_capacity_value": 120,
            "estimated_annual_cost": 60,
            "time_to_impact_months": 3,
            "discount_rate": 0,
        }
        inputs.update(overrides)
        return ValueInputs(**inputs)

    def _assessment(self) -> AssessmentInput:
        scores = [
            DimensionScore("business_value", 5, "High value"),
            DimensionScore("current_friction", 4, "Painful process"),
            DimensionScore("data_feasibility", 4, "Data available"),
            DimensionScore("technical_feasibility", 4, "Feasible"),
            DimensionScore("adoption_potential", 4, "Strong sponsor"),
            DimensionScore("risk_governance", 4, "Controlled"),
        ]
        return AssessmentInput(
            use_case_name="AI Case Processing",
            program_name="Pilot",
            scores=scores,
            value_inputs=ValueInputs(
                annual_volume=12000,
                time_saved_hours=0.3,
                hourly_cost=18,
                error_reduction_rate=0.15,
                average_error_cost=22,
                revenue_capacity_value=25000,
                estimated_annual_cost=28000,
            ),
        )

    def test_priority_score_range(self) -> None:
        score = compute_priority_score(self._assessment())
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 5.0)

    def test_value_estimates_positive(self) -> None:
        values = compute_value_estimates(self._assessment().value_inputs)
        self.assertGreater(values["estimated_gross_value"], 0)

    def test_classification_quick_win(self) -> None:
        category = classify_use_case(
            priority_score=3.35,
            risk_governance_score=3,
            readiness_average=3.8,
            business_value_score=4,
        )
        self.assertEqual(category, "Quick Win")

    def test_classification_strategic_bet_accepts_high_value_or_high_priority(self) -> None:
        by_value = classify_use_case(
            priority_score=3.6,
            risk_governance_score=4,
            readiness_average=3.79,
            business_value_score=4,
        )
        by_priority = classify_use_case(
            priority_score=4.0,
            risk_governance_score=4,
            readiness_average=3.79,
            business_value_score=3,
        )
        self.assertEqual(by_value, "Strategic Bet")
        self.assertEqual(by_priority, "Strategic Bet")

    def test_classification_foundation_reject_and_precedence_boundaries(self) -> None:
        self.assertEqual(
            classify_use_case(
                priority_score=4.4,
                risk_governance_score=4,
                readiness_average=2.99,
                business_value_score=5,
            ),
            "Foundation",
        )
        self.assertEqual(
            classify_use_case(
                priority_score=2.79,
                risk_governance_score=2,
                readiness_average=3.0,
                business_value_score=2,
            ),
            "Reject",
        )
        self.assertEqual(
            classify_use_case(
                priority_score=2.5,
                risk_governance_score=2,
                readiness_average=2.8,
                business_value_score=2,
            ),
            "Foundation",
        )

    def test_scorecard_rounding_and_readiness_average(self) -> None:
        result = compute_scorecard(
            assessment=self._assessment(),
            signals=ScoringSignals(
                duration_minutes_per_occurrence=25,
                impact_type="quantified",
                supporting_evidence_present=True,
                sponsor_present=True,
                data_availability="available",
                data_quality_score=4,
                pilot_accessibility="ready",
                sensitive_data_flag="personal",
                deployment_environment="customer_vpc",
                effort_band="medium",
                dependency_statement="aucune dépendance bloquante",
                support_owner_present=True,
                team_skills_present=True,
                training_needs_present=True,
                risk_profile="Medium",
                affected_person_decision=False,
                human_validation_required="mandatory",
                audit_logging_required=True,
                access_model="rbac",
                data_boundary="internal_only",
                value_confidence="medium",
            ),
            configuration=ScoreConfiguration(),
        )
        self.assertEqual(round(result.priority_score, 3), result.priority_score)
        self.assertEqual(
            result.readiness_average,
            compute_readiness_average(result.dimensions),
        )
        self.assertEqual(len(result.dimensions), 6)

    def test_scorecard_classification_uses_business_value_threshold(self) -> None:
        result = compute_scorecard(
            assessment=self._assessment(),
            signals=ScoringSignals(
                data_availability="available",
                data_quality_score=4,
                pilot_accessibility="ready",
                effort_band="medium",
                support_owner_present=True,
                team_skills_present=True,
                training_needs_present=True,
                risk_profile="High",
                human_validation_required="mandatory",
                value_confidence="medium",
            ),
            configuration=ScoreConfiguration(),
            manual_overrides={
                "business_value": (4, "Boundary business value"),
                "current_friction": (1, "Keep weighted priority below 4"),
                "data_feasibility": (4, "Readiness boundary"),
                "technical_feasibility": (4, "Readiness boundary"),
                "adoption_potential": (4, "Readiness boundary"),
                "risk_governance": (3, "Governance boundary"),
            },
        )
        self.assertLess(result.priority_score, 4.0)
        self.assertEqual(result.readiness_average, 4.0)
        self.assertEqual(result.category, "Quick Win")

    def test_value_assessment_scenarios_and_sensitivity(self) -> None:
        result = compute_value_assessment(
            ValueInputs(
                annual_volume=12000,
                time_saved_hours=0.2,
                hourly_cost=45,
                error_reduction_rate=20,
                average_error_cost=85,
                revenue_capacity_value=15000,
                estimated_annual_cost=25000,
                time_to_impact_months=4,
                confidence="medium",
            )
        )
        self.assertEqual(result.net_annual_value, 302000.0)
        self.assertEqual(
            [scenario.name for scenario in result.scenarios],
            ["conservative", "baseline", "optimistic"],
        )
        self.assertEqual(
            [entry.lever for entry in result.sensitivities],
            ["time_saved_hours", "error_reduction_rate", "revenue_capacity_value"],
        )

    def test_annual_units_net_and_delayed_scenarios(self) -> None:
        inputs = self._value_inputs()
        self.assertEqual(
            compute_value_estimates(inputs),
            {
                "annual_time_value": 240.0,
                "error_avoidance_value": 12.0,
                "estimated_gross_value": 372.0,
                "estimated_net_value": 312.0,
            },
        )
        result = compute_value_assessment(inputs)
        self.assertEqual(result.calculation_version, VALUE_CALCULATION_VERSION)
        self.assertEqual(result.currency, "EUR")
        self.assertEqual(
            (
                result.annual_time_value,
                result.error_avoidance_value,
                result.gross_value,
                result.net_annual_value,
                result.npv_3y,
                result.payback_months,
            ),
            (240.0, 12.0, 372.0, 312.0, 843.0, 4.0),
        )
        self.assertEqual(
            [asdict(scenario) for scenario in result.scenarios],
            [
                {
                    "name": "conservative",
                    "annual_time_value": 192.0,
                    "error_avoidance_value": 9.6,
                    "revenue_capacity_value": 96.0,
                    "gross_value": 297.6,
                    "net_annual_value": 237.6,
                    "npv_3y": 638.4,
                    "payback_months": 4.0,
                },
                {
                    "name": "baseline",
                    "annual_time_value": 240.0,
                    "error_avoidance_value": 12.0,
                    "revenue_capacity_value": 120.0,
                    "gross_value": 372.0,
                    "net_annual_value": 312.0,
                    "npv_3y": 843.0,
                    "payback_months": 4.0,
                },
                {
                    "name": "optimistic",
                    "annual_time_value": 288.0,
                    "error_avoidance_value": 14.4,
                    "revenue_capacity_value": 144.0,
                    "gross_value": 446.4,
                    "net_annual_value": 386.4,
                    "npv_3y": 1047.6,
                    "payback_months": 4.0,
                },
            ],
        )

    def test_sensitivity_changes_only_one_lever_and_includes_npv(self) -> None:
        result = compute_value_assessment(self._value_inputs())
        self.assertEqual(
            [asdict(entry) for entry in result.sensitivities],
            [
                {
                    "lever": "time_saved_hours",
                    "baseline_net_annual_value": 312.0,
                    "low_net_annual_value": 264.0,
                    "high_net_annual_value": 360.0,
                    "low_delta": -48.0,
                    "high_delta": 48.0,
                    "low_npv_3y": 711.0,
                    "high_npv_3y": 975.0,
                },
                {
                    "lever": "error_reduction_rate",
                    "baseline_net_annual_value": 312.0,
                    "low_net_annual_value": 309.6,
                    "high_net_annual_value": 314.4,
                    "low_delta": -2.4,
                    "high_delta": 2.4,
                    "low_npv_3y": 836.4,
                    "high_npv_3y": 849.6,
                },
                {
                    "lever": "revenue_capacity_value",
                    "baseline_net_annual_value": 312.0,
                    "low_net_annual_value": 288.0,
                    "high_net_annual_value": 336.0,
                    "low_delta": -24.0,
                    "high_delta": 24.0,
                    "low_npv_3y": 777.0,
                    "high_npv_3y": 909.0,
                },
            ],
        )

    def test_discounted_monthly_npv_and_payback_after_delay(self) -> None:
        result = compute_value_assessment(
            self._value_inputs(
                time_saved_hours=0,
                error_reduction_rate=0,
                discount_rate=0.10,
            )
        )
        # Three monthly costs of 5 precede 33 monthly net inflows of 5.
        # The effective monthly rate is 1.1 ** (1/12) - 1.
        self.assertEqual(result.net_annual_value, 60.0)
        self.assertEqual(result.npv_3y, 126.40)
        self.assertEqual(result.payback_months, 7.0)

    def test_zero_and_unrecovered_value_have_no_payback(self) -> None:
        zero = compute_value_assessment(
            self._value_inputs(
                annual_volume=0,
                revenue_capacity_value=0,
                estimated_annual_cost=0,
            )
        )
        self.assertEqual((zero.net_annual_value, zero.npv_3y), (0.0, 0.0))
        self.assertIsNone(zero.payback_months)
        self.assertTrue(all(scenario.payback_months is None for scenario in zero.scenarios))

        never_recovers = compute_value_assessment(
            self._value_inputs(
                annual_volume=0,
                revenue_capacity_value=120,
                estimated_annual_cost=60,
                time_to_impact_months=36,
            )
        )
        self.assertEqual(never_recovers.net_annual_value, 60.0)
        self.assertEqual(never_recovers.npv_3y, -180.0)
        self.assertIsNone(never_recovers.payback_months)

        delayed_free = compute_value_assessment(
            self._value_inputs(
                annual_volume=0,
                revenue_capacity_value=120,
                estimated_annual_cost=0,
                time_to_impact_months=3,
            )
        )
        self.assertEqual(delayed_free.payback_months, 4.0)

    def test_percent_boundary_and_half_up_cents(self) -> None:
        for rate, expected in ((0.99, 59.4), (1, 60.0), (1.01, 0.606), (100, 60.0)):
            with self.subTest(rate=rate):
                inputs = self._value_inputs(error_reduction_rate=rate)
                self.assertEqual(
                    compute_value_assessment(inputs).error_avoidance_value,
                    float(f"{expected:.2f}"),
                )
        capped = compute_value_assessment(self._value_inputs(error_reduction_rate=100))
        self.assertEqual(capped.scenarios[2].error_avoidance_value, 60.0)
        self.assertEqual(capped.sensitivities[1].high_net_annual_value, capped.net_annual_value)

        half_cent = self._value_inputs(
            annual_volume=1,
            time_saved_hours=0.0005,
            hourly_cost=10,
            error_reduction_rate=0,
            revenue_capacity_value=0,
            estimated_annual_cost=0.01,
            time_to_impact_months=0,
        )
        self.assertEqual(
            compute_value_estimates(half_cent),
            {
                "annual_time_value": 0.01,
                "error_avoidance_value": 0.0,
                "estimated_gross_value": 0.01,
                "estimated_net_value": -0.01,
            },
        )
        computed = compute_value_assessment(half_cent)
        self.assertEqual(computed.annual_time_value, 0.01)
        self.assertEqual(computed.net_annual_value, -0.01)

    def test_invalid_weights_and_missing_dimensions_raise(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly 1.00"):
            ScoreConfiguration(
                weights={
                    "business_value": 0.25,
                    "current_friction": 0.15,
                    "data_feasibility": 0.15,
                    "technical_feasibility": 0.15,
                    "adoption_potential": 0.10,
                    "risk_governance": 0.19,
                }
            )

        incomplete = AssessmentInput(
            use_case_name="Incomplete",
            program_name="Pilot",
            scores=self._assessment().scores[:-1],
            value_inputs=self._assessment().value_inputs,
        )
        with self.assertRaisesRegex(ValueError, "missing dimensions: risk_governance"):
            compute_priority_score(incomplete)

    def test_duplicate_dimension_scores_are_rejected(self) -> None:
        duplicate_scores = self._assessment().scores + [
            DimensionScore("business_value", 4, "Duplicate business value"),
        ]
        duplicated = AssessmentInput(
            use_case_name="Duplicated",
            program_name="Pilot",
            scores=duplicate_scores,
            value_inputs=self._assessment().value_inputs,
        )
        with self.assertRaisesRegex(ValueError, "duplicate dimensions: business_value"):
            compute_priority_score(duplicated)

    def test_value_inputs_require_finite_and_bounded_values(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "error_reduction_rate must be less than or equal to 100",
        ):
            ValueInputs(
                annual_volume=12000,
                time_saved_hours=0.2,
                hourly_cost=45,
                error_reduction_rate=101,
                average_error_cost=85,
                revenue_capacity_value=15000,
                estimated_annual_cost=25000,
            )

        with self.assertRaisesRegex(ValueError, "annual_volume must be finite"):
            ValueInputs(
                annual_volume=float("inf"),
                time_saved_hours=0.2,
                hourly_cost=45,
                error_reduction_rate=20,
                average_error_cost=85,
                revenue_capacity_value=15000,
                estimated_annual_cost=25000,
            )


if __name__ == "__main__":
    unittest.main()
