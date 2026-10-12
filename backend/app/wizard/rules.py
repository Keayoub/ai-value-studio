from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.api.v1.errors import AppError
from app.db.models.lifecycle import Answer, QuestionDefinition
from app.schemas.wizard import JsonValue, StepValidationError

SUPPORTED_CONDITION_OPERATORS = frozenset({"equals", "not_equals", "in", "not_in"})
SUPPORTED_FIELD_TYPES = {
    "text": {"schema_types": {"string"}},
    "textarea": {"schema_types": {"string"}},
    "number": {"schema_types": {"number"}},
    "integer": {"schema_types": {"integer"}},
    "boolean": {"schema_types": {"boolean"}},
    "select": {"schema_types": {"string"}},
    "radio": {"schema_types": {"string"}},
    "money": {"schema_types": {"number"}},
    "multiselect": {"schema_types": {"array"}},
    "list": {"schema_types": {"array"}},
    "scale_1_to_5": {"schema_types": {"integer"}},
}
SUPPORTED_SCHEMA_TYPES = frozenset({"string", "integer", "number", "boolean", "array"})

FRENCH_REQUIRED_MESSAGE = "Ce champ est obligatoire."
FRENCH_CHOOSE_OPTION_MESSAGE = "Choisissez une option pour poursuivre."
FRENCH_POSITIVE_NUMBER_MESSAGE = "Indiquez une valeur supérieure à 0."


def validate_template_field(
    *,
    key: str,
    field_type: str,
    field_schema: Mapping[str, object],
    option_values: Sequence[str],
) -> None:
    if field_type not in SUPPORTED_FIELD_TYPES:
        raise ValueError(f"Unsupported field type '{field_type}' for question '{key}'.")

    schema_type = field_schema.get("type")
    if schema_type not in SUPPORTED_SCHEMA_TYPES:
        raise ValueError(f"Unsupported schema type '{schema_type}' for question '{key}'.")

    supported_schema_types = SUPPORTED_FIELD_TYPES[field_type]["schema_types"]
    if schema_type not in supported_schema_types:
        raise ValueError(
            f"Field type '{field_type}' for question '{key}' requires schema type "
            f"{sorted(supported_schema_types)}, got '{schema_type}'."
        )

    if field_type in {"select", "radio"}:
        enum_values = field_schema.get("enum")
        if not isinstance(enum_values, list) or enum_values != list(option_values):
            raise ValueError(
                f"Question '{key}' must define a schema enum matching its options."
            )

    if field_type == "multiselect":
        items = field_schema.get("items")
        if not isinstance(items, Mapping):
            raise ValueError(f"Question '{key}' must define array items for multiselect.")
        if items.get("type") != "string":
            raise ValueError(f"Question '{key}' multiselect items must be strings.")
        enum_values = items.get("enum")
        if not isinstance(enum_values, list) or enum_values != list(option_values):
            raise ValueError(
                f"Question '{key}' must define item enum values matching its multiselect options."
            )

    if field_type == "list":
        items = field_schema.get("items")
        if not isinstance(items, Mapping) or items.get("type") != "string":
            raise ValueError(f"Question '{key}' list items must be strings.")

    if field_type == "scale_1_to_5":
        minimum = field_schema.get("minimum")
        maximum = field_schema.get("maximum")
        if minimum != 1 or maximum != 5:
            raise ValueError(
                f"Question '{key}' scale_1_to_5 must declare minimum 1 and maximum 5."
            )


def validate_template_condition(question_key: str, operator: str) -> None:
    if operator not in SUPPORTED_CONDITION_OPERATORS:
        raise ValueError(
            f"Question '{question_key}' uses unsupported conditional operator '{operator}'."
        )


def question_is_visible(question: QuestionDefinition, answers: dict[str, Answer]) -> bool:
    conditions = _conditional_rules(question).get("visible_if", [])
    return conditions_match(question.question_key, conditions, answers) if conditions else True


def question_is_required(question: QuestionDefinition, answers: dict[str, Answer]) -> bool:
    base_required = bool((question.ui_config_json or {}).get("required"))
    conditions = _conditional_rules(question).get("required_if", [])
    if conditions:
        return conditions_match(question.question_key, conditions, answers)
    return base_required


def validate_question_value(
    question: QuestionDefinition,
    value: JsonValue,
) -> StepValidationError | None:
    schema = question.validation_schema_json or {}
    schema_type = schema.get("type")
    if schema_type == "string":
        return _validate_string(question, value, schema)
    if schema_type == "integer":
        return _validate_integer(question, value, schema)
    if schema_type == "number":
        return _validate_number(question, value, schema)
    if schema_type == "boolean":
        return _validate_boolean(question, value)
    if schema_type == "array":
        return _validate_array(question, value, schema)
    _raise_misconfigured_template(
        f"Question '{question.question_key}' uses unsupported schema type '{schema_type}'."
    )


def required_message_for(field_type: str) -> str:
    if field_type in {"radio", "select", "boolean", "multiselect", "scale_1_to_5"}:
        return FRENCH_CHOOSE_OPTION_MESSAGE
    return FRENCH_REQUIRED_MESSAGE


def conditions_match(
    question_key: str,
    conditions: object,
    answers: dict[str, Answer],
) -> bool:
    if not isinstance(conditions, list):
        _raise_misconfigured_template(
            f"Question '{question_key}' has invalid conditional rules configuration."
        )
    for condition in conditions:
        if not isinstance(condition, dict):
            _raise_misconfigured_template(
                f"Question '{question_key}' has invalid conditional rule entries."
            )
        target_key = condition.get("question_key")
        operator = condition.get("operator")
        expected = condition.get("value")
        if not isinstance(target_key, str) or not isinstance(operator, str):
            _raise_misconfigured_template(
                f"Question '{question_key}' has incomplete conditional rules."
            )
        if operator not in SUPPORTED_CONDITION_OPERATORS:
            _raise_misconfigured_template(
                f"Question '{question_key}' uses unsupported conditional operator '{operator}'."
            )
        actual = _answer_value(answers, target_key)
        if not _compare_condition(actual, operator, expected):
            return False
    return True


def _validate_string(
    question: QuestionDefinition,
    value: JsonValue,
    schema: Mapping[str, object],
) -> StepValidationError | None:
    if not isinstance(value, str):
        return StepValidationError(
            question_key=question.question_key,
            message=required_message_for(question.field_type),
        )
    min_length = int(schema.get("min_length", 0))
    if len(value.strip()) < min_length:
        return StepValidationError(
            question_key=question.question_key,
            message=required_message_for(question.field_type),
        )
    max_length = schema.get("max_length")
    if isinstance(max_length, int) and len(value) > max_length:
        return StepValidationError(
            question_key=question.question_key,
            message="La réponse est trop longue.",
        )
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        return StepValidationError(
            question_key=question.question_key,
            message=FRENCH_CHOOSE_OPTION_MESSAGE,
        )
    return None


def _validate_integer(
    question: QuestionDefinition,
    value: JsonValue,
    schema: Mapping[str, object],
) -> StepValidationError | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return StepValidationError(
            question_key=question.question_key,
            message=_number_message_for(question.field_type),
        )
    minimum = schema.get("minimum")
    if isinstance(minimum, int) and value < minimum:
        return StepValidationError(
            question_key=question.question_key,
            message=_number_message_for(question.field_type),
        )
    maximum = schema.get("maximum")
    if isinstance(maximum, int) and value > maximum:
        return StepValidationError(
            question_key=question.question_key,
            message="La valeur dépasse la limite autorisée.",
        )
    return None


def _validate_number(
    question: QuestionDefinition,
    value: JsonValue,
    schema: Mapping[str, object],
) -> StepValidationError | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return StepValidationError(
            question_key=question.question_key,
            message=_number_message_for(question.field_type),
        )
    minimum = schema.get("minimum")
    if isinstance(minimum, (int, float)) and float(value) < float(minimum):
        return StepValidationError(
            question_key=question.question_key,
            message=_number_message_for(question.field_type),
        )
    exclusive_minimum = schema.get("exclusive_minimum")
    if isinstance(exclusive_minimum, (int, float)) and float(value) <= float(exclusive_minimum):
        return StepValidationError(
            question_key=question.question_key,
            message=_number_message_for(question.field_type),
        )
    maximum = schema.get("maximum")
    if isinstance(maximum, (int, float)) and float(value) > float(maximum):
        return StepValidationError(
            question_key=question.question_key,
            message="La valeur dépasse la limite autorisée.",
        )
    return None


def _validate_boolean(
    question: QuestionDefinition,
    value: JsonValue,
) -> StepValidationError | None:
    if not isinstance(value, bool):
        return StepValidationError(
            question_key=question.question_key,
            message=FRENCH_CHOOSE_OPTION_MESSAGE,
        )
    return None


def _validate_array(
    question: QuestionDefinition,
    value: JsonValue,
    schema: Mapping[str, object],
) -> StepValidationError | None:
    if not isinstance(value, list):
        return StepValidationError(
            question_key=question.question_key,
            message=required_message_for(question.field_type),
        )

    min_items = schema.get("min_items")
    if isinstance(min_items, int) and len(value) < min_items:
        return StepValidationError(
            question_key=question.question_key,
            message=required_message_for(question.field_type),
        )
    max_items = schema.get("max_items")
    if isinstance(max_items, int) and len(value) > max_items:
        return StepValidationError(
            question_key=question.question_key,
            message="La valeur dépasse la limite autorisée.",
        )

    items = schema.get("items")
    if not isinstance(items, Mapping):
        _raise_misconfigured_template(
            f"Question '{question.question_key}' uses an array schema without items."
        )
    item_type = items.get("type")
    if item_type != "string":
        _raise_misconfigured_template(
            f"Question '{question.question_key}' uses unsupported array item type '{item_type}'."
        )

    min_length = int(items.get("min_length", 0))
    enum_values = items.get("enum")
    for entry in value:
        if not isinstance(entry, str) or len(entry.strip()) < min_length:
            return StepValidationError(
                question_key=question.question_key,
                message=required_message_for(question.field_type),
            )
        if isinstance(enum_values, list) and entry not in enum_values:
            return StepValidationError(
                question_key=question.question_key,
                message=FRENCH_CHOOSE_OPTION_MESSAGE,
            )
    return None


def _conditional_rules(question: QuestionDefinition) -> dict[str, object]:
    return question.conditional_rules_json or {}


def _number_message_for(field_type: str) -> str:
    if field_type == "scale_1_to_5":
        return FRENCH_CHOOSE_OPTION_MESSAGE
    return FRENCH_POSITIVE_NUMBER_MESSAGE


def _answer_value(answers: dict[str, Answer], question_key: str) -> JsonValue | None:
    answer = answers.get(question_key)
    if answer is None:
        return None
    return answer.value_data_json


def _compare_condition(actual: JsonValue | None, operator: str, expected: object) -> bool:
    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "in" and isinstance(expected, list):
        return actual in expected
    if operator == "not_in" and isinstance(expected, list):
        return actual not in expected
    _raise_misconfigured_template(f"Unsupported conditional operator '{operator}'.")


def _raise_misconfigured_template(detail: str) -> None:
    raise AppError(
        status_code=500,
        title="Internal Server Error",
        detail=detail,
    )
