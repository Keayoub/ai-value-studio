from __future__ import annotations

import argparse
import json
from pathlib import Path

from .documents import render_amoa_implementation_plan
from .llm_kickstart import KickstartService, RuleBasedKickstartProvider
from .models import (
    AssessmentInput,
    DimensionScore,
    LlmKickstartInput,
    UseCaseProfile,
    ValueInputs,
)
from .scoring import classify_use_case, compute_priority_score, compute_value_estimates


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Value Studio Framework CLI")
    parser.add_argument("--input", required=True, help="Path to JSON input file")
    parser.add_argument("--output", required=True, help="Path to markdown output")
    parser.add_argument("--kickstart", action="store_true", help="Use LLM kickstart draft")
    parser.add_argument("--lang", default="fr", choices=["fr", "en"], help="Output language")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))

    scores = [DimensionScore(**s) for s in payload["scores"]]
    value_inputs = ValueInputs(**payload["value_inputs"])
    assessment = AssessmentInput(
        use_case_name=payload["use_case_name"],
        program_name=payload.get("program_name", "Default Program"),
        scores=scores,
        value_inputs=value_inputs,
    )

    priority_score = compute_priority_score(assessment)
    value_estimates = compute_value_estimates(value_inputs)
    readiness_avg = (
        payload.get("readiness_average")
        or sum(s.value for s in scores if s.dimension != "risk_governance") / (len(scores) - 1)
    )
    risk_score = next(s.value for s in scores if s.dimension == "risk_governance")
    category = classify_use_case(priority_score, risk_score, readiness_avg)

    profile = UseCaseProfile(**payload["use_case_profile"])

    kickstart_out = None
    if args.kickstart:
        service = KickstartService(RuleBasedKickstartProvider(language=args.lang))
        kickstart_out = service.kickoff(LlmKickstartInput(**payload["kickstart_input"]))

    document = render_amoa_implementation_plan(
        profile=profile,
        value_estimates=value_estimates,
        priority_score=priority_score,
        category=category,
        kickstart=kickstart_out,
        language=args.lang,
    )

    Path(args.output).write_text(document, encoding="utf-8")
    print(f"Generated {args.output}")


if __name__ == "__main__":
    main()
