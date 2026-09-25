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
    language: str = "fr",
) -> str:
    if language not in {"fr", "en"}:
        raise ValueError("language must be 'fr' or 'en'")

    today = datetime.utcnow().strftime("%Y-%m-%d")
    ai_marker = ("Oui" if kickstart is not None else "Non") if language == "fr" else ("Yes" if kickstart is not None else "No")

    risks = "\n".join(f"- {r}" for r in profile.key_risks)
    deps = "\n".join(f"- {d}" for d in profile.dependencies)
    kpis = "\n".join(f"- {k}" for k in profile.kpis)

    if language == "fr":
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

    return f"""# AMOA Use Case Implementation Plan

## Metadata
- Date: {today}
- Organization: {profile.organization}
- Program: AI Value Studio
- Department: {profile.department}
- Owner: {profile.owner}
- AI-assisted kickstart: {ai_marker}

## 1) Business framing
- Use case title: {profile.title}
- Problem statement: {profile.problem_statement}
- Proposed AI solution: {profile.ai_solution}
- Required human validation: {profile.required_human_validation}

## 2) Estimated business value
- Annual Time Value: {value_estimates['annual_time_value']}
- Error Avoidance Value: {value_estimates['error_avoidance_value']}
- Estimated Gross Value: {value_estimates['estimated_gross_value']}
- Estimated Net Value: {value_estimates['estimated_net_value']}
- Priority Score: {priority_score}
- Portfolio category: {category}

## 3) Pilot KPIs
{kpis}

## 4) IS and organizational dependencies
{deps}

## 5) Governance & risks
{risks}

## 6) Implementation plan
### Phase 1 — Discovery & Design (Weeks 1-2)
- Validate hypotheses and scope
- Map data and business rules
- Define human-in-the-loop protocol

### Phase 2 — Pilot Build (Weeks 3-6)
- Implement assisted AI flow
- Test quality, security, and compliance
- Train pilot users

### Phase 3 — Go/No-Go & Scale (Weeks 7-8)
- Measure target KPIs vs baseline
- Decide Go/Defer/Reject
- Prepare industrialization roadmap

## 7) Decision and validation
- Decision sponsor: __________________
- Decision: Go / Pilot / Defer / Reject
- Review date: __________________
"""
