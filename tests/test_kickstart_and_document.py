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

    def test_amoa_document_contains_sections_fr(self) -> None:
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
            language="fr",
        )
        self.assertIn("# AMOA Use Case Implementation Plan", doc)
        self.assertIn("## 6) Plan de mise en place", doc)

    def test_amoa_document_contains_sections_en(self) -> None:
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
            language="en",
        )
        self.assertIn("## Metadata", doc)
        self.assertIn("## 6) Implementation plan", doc)

    def test_kickstart_provider_en(self) -> None:
        service = KickstartService(RuleBasedKickstartProvider(language="en"))
        out = service.kickoff(
            LlmKickstartInput(
                strategic_objective="Reduce claim processing lead time",
                target_process="Claims qualification",
                current_friction="Manual checks create backlog",
                impacted_department="Operations",
                critical_constraints="Data residency in Morocco",
            )
        )
        self.assertIn("creates major friction", out.problem_statement)

    def test_kickstart_rejects_sensitive_input(self) -> None:
        service = KickstartService(RuleBasedKickstartProvider(language="fr"))
        with self.assertRaises(ValueError):
            service.kickoff(
                LlmKickstartInput(
                    strategic_objective="Improve workflow",
                    target_process="Claims",
                    current_friction="Contact: jane.doe@company.com",
                    impacted_department="Operations",
                    critical_constraints="None",
                )
            )

    def test_kickstart_rejects_too_long_input(self) -> None:
        with self.assertRaises(ValueError):
            LlmKickstartInput(
                strategic_objective="x" * 801,
                target_process="Claims",
                current_friction="Manual backlog",
                impacted_department="Operations",
                critical_constraints="None",
            )


if __name__ == "__main__":
    unittest.main()
