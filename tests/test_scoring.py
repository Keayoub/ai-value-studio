import unittest

from ai_value_studio.models import AssessmentInput, DimensionScore, ValueInputs
from ai_value_studio.scoring import classify_use_case, compute_priority_score, compute_value_estimates


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
        category = classify_use_case(priority_score=4.2, risk_governance_score=4, readiness_average=4.0)
        self.assertEqual(category, "Quick Win")


if __name__ == "__main__":
    unittest.main()
