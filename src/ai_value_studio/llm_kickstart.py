from __future__ import annotations

from typing import Protocol

from .models import LlmKickstartInput, LlmKickstartOutput


class KickstartProvider(Protocol):
    def generate(self, payload: LlmKickstartInput) -> LlmKickstartOutput:
        ...


class RuleBasedKickstartProvider:
    """Deterministic fallback provider used before wiring a live LLM."""

    def generate(self, payload: LlmKickstartInput) -> LlmKickstartOutput:
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
        return self.provider.generate(payload)
