# AI Value Studio

## From AI ideas to business value

TIFINIA AI Value Studio is a reusable AI advisory and assessment framework for turning business problems into prioritized, measurable and governable AI use cases.

It supports the full path:

```text
Business discovery → Use case definition → Value assessment → Readiness → Governance → Prioritization → Pilot → Scale
```

## What is included

- AI Use Case Canvas
- Business Value Scorecard
- AI Portfolio Matrix
- Executive AI Opportunity Brief
- AMOA Use Case Implementation Plan (mise en place)
- Product brief and commercial packaging
- [Functional specifications](docs/FUNCTIONAL_SPECIFICATIONS_FR.md) for the Web wizard, assessment engine and document generation
- [Coding agent brief](docs/CODING_AGENT_BRIEF_FR.md) for the MVP implementation scope and acceptance criteria

## Positioning

AI Value Studio is the AMOA and decision layer that helps organizations select the right AI opportunities before investing in technology. Validated use cases can then connect to TIFINIA AI Platform, Agent Studio and vertical solutions.

## Framework dimensions

Each use case is assessed across:

- business value;
- current friction;
- data readiness;
- technical feasibility;
- adoption potential;
- risk and governance.

## Commercial offers

### AI Value Discovery Sprint

A 1–2 week discovery to identify and qualify 5–10 AI opportunities.

### AI Portfolio & Business Case Assessment

A 3–5 week assessment to prioritize use cases, estimate value and build the roadmap.

### AI Pilot Activation

A 6–12 week engagement to turn one prioritized use case into an operational pilot.

## Repository structure

```text
commercial-assets/
└── product-frameworks/
    ├── TIFINIA_AI_VALUE_STUDIO_PRODUCT_BRIEF_FR.md
    └── templates/
        ├── AI_USE_CASE_CANVAS_FR.md
        ├── AI_VALUE_SCORECARD_FR.md
        ├── AI_PORTFOLIO_MATRIX_FR.md
        ├── EXECUTIVE_AI_OPPORTUNITY_BRIEF_FR.md
        └── AMOA_USE_CASE_IMPLEMENTATION_PLAN_FR.md
```

## Framework implementation (v0.1)

This repository now includes a runnable core implementation under `src/ai_value_studio/` with:

- weighted scoring engine (priority + category),
- value estimation formulas,
- optional LLM kickstart service abstraction (with deterministic fallback provider),
- AMOA implementation-plan document generator,
- bilingual framework support (French/English),
- CLI to generate a full AMOA markdown deliverable from JSON input.

### Quick run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m ai_value_studio.cli --input examples/sample_use_case.json --output outputs/amoa_plan.md --kickstart
```

### Tests

```bash
python -m pytest
```

## Operating model

- **Co-editing**: oui, tu peux co-éditer les livrables (wizard output, AMOA, BVA) avec ton équipe puis regénérer une nouvelle version.
- **Copilot**: utile pour accélérer le dev, pas obligatoire pour l’usage métier du framework.
- **Hermes Agent**: recommandé pour l’orchestration autonome (analyse, génération, itérations Kaizen), mais non obligatoire pour exécuter le framework localement.

## Status

Framework v0.1 — reusable consulting assets + runnable core engine foundation (FR/EN + Kaizen roadmap).

## MVP validation

The integrated MVP is validated with:

```bash
pytest -q
cd web && npm run lint && npm run build
```

The Python test suite, web lint, and production build must pass before publishing a release.
