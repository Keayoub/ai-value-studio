from __future__ import annotations

from collections.abc import Sequence

from app.wizard.rules import validate_template_condition, validate_template_field
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TemplateCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_key: str = Field(min_length=1, max_length=120)
    operator: str = Field(min_length=1, max_length=32)
    value: object


class TemplateOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=200)


class TemplateQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    key: str = Field(min_length=1, max_length=120)
    field_type: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=300)
    help_text: str | None = Field(default=None, max_length=2000)
    placeholder: str | None = Field(default=None, max_length=300)
    options: list[TemplateOption] = Field(default_factory=list)
    field_schema: dict[str, object] = Field(alias="schema", serialization_alias="schema")
    required: bool = False
    visible_if: list[TemplateCondition] = Field(default_factory=list)
    required_if: list[TemplateCondition] = Field(default_factory=list)
    contributor_editable: bool = True


class TemplateStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0, le=8)
    key: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=2000)
    available: bool = True
    optional: bool = False
    questions: list[TemplateQuestion] = Field(default_factory=list)


class WizardTemplateSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_key: str = Field(min_length=1, max_length=80)
    version: int = Field(ge=1)
    locale: str = Field(min_length=2, max_length=16)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    steps: list[TemplateStep]

    @model_validator(mode="after")
    def validate_template(self) -> WizardTemplateSeed:
        expected_steps = list(range(0, 9))
        actual_steps = [step.index for step in self.steps]
        if actual_steps != expected_steps:
            raise ValueError("Template must define steps 0 through 8 in order.")

        question_keys: set[str] = set()
        for step in self.steps:
            seen_in_step: set[str] = set()
            for question in step.questions:
                if question.key in question_keys:
                    raise ValueError(f"Duplicate question key '{question.key}'.")
                if question.key in seen_in_step:
                    raise ValueError(
                        f"Duplicate question key '{question.key}' within step {step.index}."
                    )
                seen_in_step.add(question.key)
                question_keys.add(question.key)

                if (
                    question.field_type in {"select", "radio", "multiselect"}
                    and not question.options
                ):
                    raise ValueError(
                        f"Question '{question.key}' must define options for field type "
                        f"'{question.field_type}'."
                    )
                if question.field_type == "boolean" and question.options:
                    raise ValueError(
                        f"Boolean question '{question.key}' cannot define explicit options."
                    )
                validate_template_field(
                    key=question.key,
                    field_type=question.field_type,
                    field_schema=question.field_schema,
                    option_values=[option.value for option in question.options],
                )

                self._validate_condition_targets(
                    question.visible_if,
                    question_keys,
                    source_question_key=question.key,
                )
                self._validate_condition_targets(
                    question.required_if,
                    question_keys,
                    source_question_key=question.key,
                )
        return self

    @staticmethod
    def _validate_condition_targets(
        conditions: Sequence[TemplateCondition],
        known_question_keys: set[str],
        *,
        source_question_key: str,
    ) -> None:
        for condition in conditions:
            if condition.question_key not in known_question_keys:
                raise ValueError(
                    f"Condition references unknown prior question '{condition.question_key}'."
                )
            validate_template_condition(source_question_key, condition.operator)
