import unittest

from ai_value_studio.models import (
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
