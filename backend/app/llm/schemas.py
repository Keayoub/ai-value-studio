from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    StringConstraints,
)

ProposalKpiItem = Annotated[str, StringConstraints(strict=True, min_length=3, max_length=120)]
ProposalNarrativeItem = Annotated[
    str,
    StringConstraints(strict=True, min_length=8, max_length=400),
]


class KickstartProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source: Literal["ai_assisted"] = "ai_assisted"
    problem_statement: StrictStr = Field(min_length=20, max_length=2000)
    ai_solution: StrictStr = Field(min_length=20, max_length=2000)
    kpi_proposals: list[ProposalKpiItem] = Field(min_length=1, max_length=5)
    value_hypotheses: list[ProposalNarrativeItem] = Field(min_length=1, max_length=5)
    risks: list[ProposalNarrativeItem] = Field(min_length=1, max_length=5)
    missing_info: list[ProposalNarrativeItem] = Field(min_length=1, max_length=6)


class KickstartPromptContext(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    workspace_name: StrictStr = Field(min_length=1, max_length=200)
    workspace_language: StrictStr = Field(min_length=2, max_length=16)
    use_case_title: StrictStr = Field(min_length=1, max_length=200)
    program_name: StrictStr = Field(min_length=1, max_length=200)
    department: StrictStr | None = Field(default=None, max_length=200)
    target_process: StrictStr = Field(min_length=3, max_length=1200)
    team_name: StrictStr | None = Field(default=None, max_length=200)
    trigger_event: StrictStr | None = Field(default=None, max_length=240)
    process_steps: list[StrictStr] = Field(default_factory=list, max_length=8)
    systems_involved: list[StrictStr] = Field(default_factory=list, max_length=8)
    annual_volume: StrictInt | None = Field(default=None, ge=1, le=100000000)
    duration_minutes_per_occurrence: float | None = Field(default=None, gt=0, le=100000)
    problem_statement: StrictStr | None = Field(default=None, max_length=2000)
    delay_cost_risk_causes: StrictStr | None = Field(default=None, max_length=2000)
    impact_statement: StrictStr | None = Field(default=None, max_length=2000)
    cost_of_inaction: StrictStr | None = Field(default=None, max_length=1200)
    ai_task: StrictStr | None = Field(default=None, max_length=1500)
    autonomy_level: StrictStr | None = Field(default=None, max_length=120)
    human_validation_policy: StrictStr | None = Field(default=None, max_length=120)
    primary_kpi: StrictStr | None = Field(default=None, max_length=255)
    kpi_target: StrictStr | None = Field(default=None, max_length=255)
    value_hypothesis: StrictStr | None = Field(default=None, max_length=1500)
    data_sources: list[StrictStr] = Field(default_factory=list, max_length=8)
    data_availability: StrictStr | None = Field(default=None, max_length=120)
    deployment_environment: StrictStr | None = Field(default=None, max_length=120)
    sensitive_data_flag: StrictStr | None = Field(default=None, max_length=120)
    compliance_constraints: StrictStr | None = Field(default=None, max_length=1500)
    risk_hypothesis: StrictStr | None = Field(default=None, max_length=1500)
    prohibited_behaviour: StrictStr | None = Field(default=None, max_length=1200)
    missing_knowledge: StrictStr | None = Field(default=None, max_length=1500)
    existing_problem_statement: StrictStr | None = Field(default=None, max_length=2000)
    existing_ai_solution: StrictStr | None = Field(default=None, max_length=2000)
    existing_primary_kpi: StrictStr | None = Field(default=None, max_length=255)
    existing_value_hypothesis: StrictStr | None = Field(default=None, max_length=1500)
    existing_risk_hypothesis: StrictStr | None = Field(default=None, max_length=1500)
    existing_missing_knowledge: StrictStr | None = Field(default=None, max_length=1500)


class KickstartPromptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_name: StrictStr = Field(min_length=1, max_length=120)
    system_prompt: StrictStr = Field(min_length=1)
    user_prompt: StrictStr = Field(min_length=1)
    response_schema: dict[str, Any]


class LlmTokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: StrictInt = Field(ge=0)
    completion_tokens: StrictInt = Field(ge=0)
    total_tokens: StrictInt = Field(ge=0)


class KickstartProviderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: StrictStr = Field(min_length=1, max_length=200)
    raw_text: StrictStr = Field(min_length=1)
    payload: dict[str, Any] | None = None
    usage: LlmTokenUsage | None = None


class KickstartSuggestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: KickstartProposal
    provider: StrictStr = Field(min_length=1, max_length=64)
    model: StrictStr = Field(min_length=1, max_length=200)
    generated_at: datetime


class KickstartAnswerApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: StrictStr | list[StrictStr]
    confirm_overwrite_ai_assisted: StrictBool = False
