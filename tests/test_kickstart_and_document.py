import unittest

from ai_value_studio.documents import render_amoa_implementation_plan
from ai_value_studio.llm_kickstart import KickstartService, RuleBasedKickstartProvider
from ai_value_studio.models import LlmKickstartInput, UseCaseProfile


class KickstartDocumentTests(unittest.TestCase):
    def test_kickstart_output_ai_assisted(self) -> None:
        service = KickstartService(RuleBasedKickstartProvider())
        out = service.kickoff(
            LlmKickstartInput(
                strategic_objective="Reduce claim processing lead time",
                target_process="Claims qualification",
                current_friction="Manual checks create backlog",
                impacted_department="Operations",
                critical_constraints="Data residency in Morocco",
            )
        )
        self.assertTrue(out.ai_assisted)
        self.assertGreaterEqual(len(out.suggested_kpis), 1)

    def test_amoa_document_contains_sections(self) -> None:
        profile = UseCaseProfile(
            title="Claims AI Triage",
            organization="Mutuelle Atlas",
            department="Operations",
            owner="Head of Claims",
            problem_statement="Backlog and high manual workload",
            ai_solution="AI-assisted triage and missing-doc detection",
            required_human_validation="Mandatory for reject decisions",
            key_risks=["Data leakage", "Wrong recommendations"],
            dependencies=["Claims API", "Document repository"],
            kpis=["Lead time", "Error rate"],
        )
        doc = render_amoa_implementation_plan(
            profile=profile,
            value_estimates={
                "annual_time_value": 10.0,
                "error_avoidance_value": 20.0,
                "estimated_gross_value": 30.0,
                "estimated_net_value": 15.0,
            },
            priority_score=4.1,
            category="Quick Win",
            kickstart=None,
        )
        self.assertIn("# AMOA Use Case Implementation Plan", doc)
        self.assertIn("## 6) Plan de mise en place", doc)


if __name__ == "__main__":
    unittest.main()
