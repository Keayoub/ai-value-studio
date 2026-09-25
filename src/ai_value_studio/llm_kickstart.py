from __future__ import annotations

import re
from typing import Protocol

from .models import LlmKickstartInput, LlmKickstartOutput

SENSITIVE_PATTERNS = (
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
)


class KickstartProvider(Protocol):
    def generate(self, payload: LlmKickstartInput) -> LlmKickstartOutput:
        ...


class RuleBasedKickstartProvider:
    """Deterministic fallback provider used before wiring a live LLM."""

    def __init__(self, language: str = "fr") -> None:
        if language not in {"fr", "en"}:
            raise ValueError("language must be 'fr' or 'en'")
        self.language = language

    def generate(self, payload: LlmKickstartInput) -> LlmKickstartOutput:
        if self.language == "en":
            return LlmKickstartOutput(
                problem_statement=(
                    f"The process '{payload.target_process}' creates major friction for "
                    f"{payload.impacted_department}: {payload.current_friction}."
                ),
                ai_solution_proposal=(
                    "Implement a supervised AI assistant that structures inputs, "
                    "proposes recommendations, and enforces mandatory human review."
                ),
                suggested_kpis=[
                    "Average processing time",
                    "Operational error rate",
                    "First-pass complete-case rate",
                ],
                value_hypotheses=[
                    "20-40% reduction in processing time",
                    "Reduced cost of critical errors",
                ],
                initial_risks=[
                    "Insufficient data quality",
                    "Over-automation risk without human control",
                    payload.critical_constraints,
                ],
                missing_information=[
                    "Exact 12-month KPI baseline",
                    "Complete inventory of data sources",
                    "Blocking business rules to document",
                ],
            )

        return LlmKickstartOutput(
            problem_statement=(
                f"Le processus '{payload.target_process}' crée une friction majeure pour "
                f"{payload.impacted_department}: {payload.current_friction}."
            ),
            ai_solution_proposal=(
                "Mettre en place un assistant IA supervisé qui structure les entrées, "
                "propose des recommandations et applique un contrôle humain obligatoire."
            ),
            suggested_kpis=[
                "Temps moyen de traitement",
                "Taux d'erreur opérationnelle",
                "Taux de dossiers complets au premier passage",
            ],
            value_hypotheses=[
                "Réduction de 20-40% du temps de traitement",
                "Réduction du coût des erreurs critiques",
            ],
            initial_risks=[
                "Qualité des données insuffisante",
                "Risque de sur-automatisation sans contrôle humain",
                payload.critical_constraints,
            ],
            missing_information=[
                "Baseline KPI exacte sur 12 mois",
                "Inventaire complet des sources de données",
                "Règles métier bloquantes à documenter",
            ],
        )


class KickstartService:
    def __init__(self, provider: KickstartProvider) -> None:
        self.provider = provider

    def kickoff(self, payload: LlmKickstartInput) -> LlmKickstartOutput:
        self._assert_safe_summary_input(payload)
        return self.provider.generate(payload)

    @staticmethod
    def _assert_safe_summary_input(payload: LlmKickstartInput) -> None:
        values = [
            payload.strategic_objective,
            payload.target_process,
            payload.current_friction,
            payload.impacted_department,
            payload.critical_constraints,
        ]
        for value in values:
            for pattern in SENSITIVE_PATTERNS:
                if pattern.search(value):
                    raise ValueError(
                        "Sensitive/raw organizational data detected in kickstart input. Provide a short, non-sensitive summary only."
                    )
