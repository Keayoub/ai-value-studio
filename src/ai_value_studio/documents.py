from __future__ import annotations

from datetime import datetime
from typing import Dict

from .models import LlmKickstartOutput, UseCaseProfile


def render_amoa_implementation_plan(
    profile: UseCaseProfile,
    value_estimates: Dict[str, float],
    priority_score: float,
    category: str,
    kickstart: LlmKickstartOutput | None = None,
) -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    ai_marker = "Oui" if kickstart is not None else "Non"

    risks = "
".join(f"- {r}" for r in profile.key_risks)
    deps = "
".join(f"- {d}" for d in profile.dependencies)
    kpis = "
".join(f"- {k}" for k in profile.kpis)

    return f"""# AMOA Use Case Implementation Plan

## Métadonnées
- Date: {today}
- Organisation: {profile.organization}
- Programme: AI Value Studio
- Département: {profile.department}
- Owner: {profile.owner}
- AI-assisted kickstart: {ai_marker}

## 1) Cadrage métier
- Titre du use case: {profile.title}
- Problem statement: {profile.problem_statement}
- Solution IA proposée: {profile.ai_solution}
- Validation humaine obligatoire: {profile.required_human_validation}

## 2) Valeur business estimée
- Annual Time Value: {value_estimates['annual_time_value']}
- Error Avoidance Value: {value_estimates['error_avoidance_value']}
- Estimated Gross Value: {value_estimates['estimated_gross_value']}
- Estimated Net Value: {value_estimates['estimated_net_value']}
- Priority Score: {priority_score}
- Catégorie portefeuille: {category}

## 3) KPI de pilotage
{kpis}

## 4) Dépendances SI et organisationnelles
{deps}

## 5) Gouvernance & risques
{risks}

## 6) Plan de mise en place
### Phase 1 — Discovery & Design (Semaines 1-2)
- Valider les hypothèses et le périmètre
- Cartographier données + règles métier
- Définir protocole human-in-the-loop

### Phase 2 — Pilot Build (Semaines 3-6)
- Implémenter flux IA assisté
- Tester qualité, sécurité, conformité
- Former utilisateurs pilotes

### Phase 3 — Go/No-Go & Scale (Semaines 7-8)
- Mesurer KPI cibles vs baseline
- Décider Go/Defer/Reject
- Préparer feuille de route d'industrialisation

## 7) Décision et validation
- Sponsor décision: __________________
- Décision: Go / Pilot / Defer / Reject
- Date de revue: __________________
"""
