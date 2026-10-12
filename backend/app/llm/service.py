from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from app.api.v1.errors import AppError
from app.audit.service import AuditService
from app.config import LlmProviderKind, Settings, get_settings
from app.db.models.lifecycle import Answer, Program, UseCase
from app.llm.contracts import (
    LlmProvider,
    LlmProviderConfigurationError,
    LlmProviderError,
    LlmProviderRateLimitError,
    LlmProviderResponseError,
    LlmProviderTimeoutError,
)
from app.llm.models import LlmCircuitBreaker, LlmRateLimitBucket
from app.llm.prompts.kickstart_fr import (
    KICKSTART_REPAIR_PROMPT,
    KICKSTART_SYSTEM_PROMPT,
    PROMPT_TEMPLATE_NAME,
)
from app.llm.providers.anthropic import AnthropicProvider
from app.llm.providers.azure_openai import AzureOpenAIProvider
from app.llm.providers.openai import OpenAIProvider
from app.llm.schemas import (
    KickstartPromptContext,
    KickstartPromptRequest,
    KickstartProposal,
    KickstartProviderResponse,
    KickstartSuggestionResponse,
)
from app.security.roles import ProductRole
from app.security.tenancy import WorkspaceContext
from app.wizard.service import AssessmentBundle, WizardService
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session

logger = logging.getLogger(__name__)
PII_SECRET_PATTERNS = (
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|rk)-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(?:api[_ -]?key|secret|password|token)\b\s*[:=]\s*\S+"),
)
FIELD_LENGTH_LIMITS = {
    "short": 255,
    "medium": 1200,
    "long": 2000,
}


def llm_provider_is_configured(settings: Settings | None = None) -> bool:
    try:
        return _build_provider(settings or get_settings()).is_configured()
    except LlmProviderConfigurationError:
        return False


class LlmAssistanceService:
    def __init__(
        self,
        session: Session,
        context: WorkspaceContext,
        request_id: str,
        provider: LlmProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.context = context
        self.request_id = request_id
        self.settings = settings or get_settings()
        self.provider = provider or _build_provider(self.settings)
        self.audit = AuditService(session)

    def generate_kickstart(
        self,
        *,
        assessment_id: str,
        expected_use_case_id: uuid.UUID,
        program: Program,
        use_case: UseCase,
    ) -> KickstartSuggestionResponse:
        self._ensure_consultant_role()
        self._ensure_enabled()
        self._ensure_provider_configured()
        self._enforce_circuit_breaker()
        self._enforce_rate_limit()

        bundle = WizardService(
            self.session,
            self.context,
            self.request_id,
        ).load_assessment_bundle(
            assessment_id=assessment_id,
            expected_use_case_id=expected_use_case_id,
        )
        prompt_context = self._build_prompt_context(
            bundle=bundle,
            program=program,
            use_case=use_case,
        )
        request = KickstartPromptRequest(
            template_name=PROMPT_TEMPLATE_NAME,
            system_prompt=KICKSTART_SYSTEM_PROMPT,
            user_prompt=prompt_context.model_dump_json(indent=2),
            response_schema=KickstartProposal.model_json_schema(),
        )
        started_at = datetime.now(UTC)
        try:
            provider_response = self.provider.generate_kickstart(request)
            proposal = self._validate_provider_response(request, provider_response)
        except AppError:
            raise
        except LlmProviderRateLimitError as exc:
            self._record_provider_failure("provider-rate-limit")
            self._log_provider_failure(
                assessment_id=str(bundle.assessment.id),
                code="provider-rate-limit",
            )
            self._audit_attempt(
                bundle=bundle,
                prompt_context=prompt_context,
                outcome="provider-rate-limit",
                started_at=started_at,
            )
            raise AppError(
                status_code=429,
                title="Too Many Requests",
                detail=(
                    "L’assistance IA est temporairement limitée. Réessayez dans quelques minutes."
                ),
            ) from exc
        except LlmProviderTimeoutError as exc:
            self._record_provider_failure("timeout")
            self._log_provider_failure(
                assessment_id=str(bundle.assessment.id),
                code="timeout",
            )
            self._audit_attempt(
                bundle=bundle,
                prompt_context=prompt_context,
                outcome="timeout",
                started_at=started_at,
            )
            raise AppError(
                status_code=504,
                title="Gateway Timeout",
                detail=(
                    "L’assistance IA n’a pas répondu à temps. Réessayez avec un "
                    "contexte plus court."
                ),
            ) from exc
        except LlmProviderError as exc:
            self._record_provider_failure(exc.code)
            self._log_provider_failure(
                assessment_id=str(bundle.assessment.id),
                code=exc.code,
            )
            self._audit_attempt(
                bundle=bundle,
                prompt_context=prompt_context,
                outcome=exc.code,
                started_at=started_at,
            )
            raise AppError(
                status_code=502,
                title="Bad Gateway",
                detail=(
                    "L’assistance IA a échoué sans résultat exploitable. Vérifiez les champs clés "
                    "et réessayez."
                ),
            ) from exc

        self._record_provider_success()
        self._audit_attempt(
            bundle=bundle,
            prompt_context=prompt_context,
            outcome="success",
            started_at=started_at,
            proposal=proposal,
            provider_response=provider_response,
        )
        return KickstartSuggestionResponse(
            proposal=proposal,
            provider=self.provider.provider_name,
            model=provider_response.model,
            generated_at=datetime.now(UTC),
        )

    def _validate_provider_response(
        self,
        request: KickstartPromptRequest,
        provider_response: KickstartProviderResponse,
    ) -> KickstartProposal:
        validation_errors: list[str] = []
        if provider_response.payload is not None:
            try:
                return KickstartProposal.model_validate(provider_response.payload)
            except ValidationError as exc:
                validation_errors = [error["msg"] for error in exc.errors()]
        else:
            validation_errors = ["Provider response was not valid JSON."]

        repaired_response = self.provider.repair_kickstart(
            request,
            provider_response.raw_text,
            validation_errors,
        )
        try:
            if repaired_response.payload is None:
                raise LlmProviderResponseError()
            return KickstartProposal.model_validate(repaired_response.payload)
        except (ValidationError, LlmProviderResponseError) as exc:
            raise LlmProviderResponseError(
                "The provider response remained invalid after one repair attempt."
            ) from exc

    def _ensure_consultant_role(self) -> None:
        role = ProductRole(self.context.membership.role)
        if role != ProductRole.CONSULTANT:
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail="Only a consultant can request AI kickstart assistance.",
            )

    def _ensure_enabled(self) -> None:
        workspace = self.context.workspace
        if not workspace.ai_assistance_enabled:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail=(
                    "L’assistance IA est désactivée pour cet espace. Un administrateur doit "
                    "activer l’option et enregistrer la note de traitement des données."
                ),
            )

    def _ensure_provider_configured(self) -> None:
        if self.provider.is_configured():
            return
        raise AppError(
            status_code=503,
            title="Service Unavailable",
            detail=(
                "L’assistance IA est activée, mais aucun fournisseur n’est configuré côté "
                "serveur pour le moment."
            ),
        )

    def _enforce_rate_limit(self) -> None:
        actor_subject_id = self.context.actor.identity_subject_id
        if actor_subject_id is None:
            raise AppError(status_code=401, title="Unauthorized", detail="Identity missing.")
        now = datetime.now(UTC)
        window_start = _window_start(now, self.settings.llm_rate_limit_window_seconds)
        table = LlmRateLimitBucket.__table__
        values = {
            "workspace_id": self.context.workspace.id,
            "actor_subject_id": actor_subject_id,
            "bucket_start": window_start,
            "request_count": 1,
            "created_at": now,
            "updated_at": now,
        }
        dialect = self.session.get_bind().dialect.name
        if dialect == "postgresql":
            statement = (
                postgresql_insert(table)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=["workspace_id", "actor_subject_id", "bucket_start"],
                    set_={
                        "request_count": table.c.request_count + 1,
                        "updated_at": now,
                    },
                )
                .returning(table.c.request_count)
            )
        else:
            statement = (
                sqlite_insert(table)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=["workspace_id", "actor_subject_id", "bucket_start"],
                    set_={
                        "request_count": table.c.request_count + 1,
                        "updated_at": now,
                    },
                )
                .returning(table.c.request_count)
            )
        count = self.session.execute(statement).scalar_one()
        if count > self.settings.llm_rate_limit_requests:
            raise AppError(
                status_code=429,
                title="Too Many Requests",
                detail=(
                    "La limite d’usage de l’assistance IA pour cet espace et cet utilisateur a "
                    "été atteinte. Réessayez plus tard."
                ),
            )

    def _enforce_circuit_breaker(self) -> None:
        breaker = self._get_circuit_breaker()
        if breaker is None or breaker.opened_until is None:
            return
        if breaker.opened_until <= datetime.now(UTC):
            return
        raise AppError(
            status_code=503,
            title="Service Unavailable",
            detail=(
                "L’assistance IA est temporairement indisponible après plusieurs échecs du "
                "fournisseur. Réessayez dans quelques minutes."
            ),
        )

    def _record_provider_failure(self, code: str) -> None:
        now = datetime.now(UTC)
        breaker = self._get_circuit_breaker()
        if breaker is None:
            breaker = LlmCircuitBreaker(
                workspace_id=self.context.workspace.id,
                provider=self.provider.provider_name,
            )
        breaker.consecutive_failures += 1
        breaker.last_failure_code = code
        breaker.last_failure_at = now
        if breaker.consecutive_failures >= self.settings.llm_circuit_breaker_failures:
            breaker.opened_until = now + timedelta(
                seconds=self.settings.llm_circuit_breaker_open_seconds
            )
        self.session.add(breaker)

    def _record_provider_success(self) -> None:
        breaker = self._get_circuit_breaker()
        if breaker is None:
            return
        breaker.consecutive_failures = 0
        breaker.last_failure_code = None
        breaker.last_failure_at = None
        breaker.opened_until = None
        self.session.add(breaker)

    def _get_circuit_breaker(self) -> LlmCircuitBreaker | None:
        return self.session.exec(
            select(LlmCircuitBreaker).where(
                LlmCircuitBreaker.workspace_id == self.context.workspace.id,
                LlmCircuitBreaker.provider == self.provider.provider_name,
            )
        ).first()

    def _build_prompt_context(
        self,
        *,
        bundle: AssessmentBundle,
        program: Program,
        use_case: UseCase,
    ) -> KickstartPromptContext:
        answers = bundle.answers
        values = {
            "workspace_name": _bound_string(self.context.workspace.name, "short"),
            "workspace_language": _bound_string(self.context.workspace.default_language, "short"),
            "use_case_title": _bound_string(use_case.title, "short"),
            "program_name": _bound_string(program.name, "short"),
            "department": _optional_bound_string(use_case.department, "short"),
            "target_process": _required_answer_string(answers, "target_process", "long"),
            "team_name": _optional_answer_string(answers, "team_name", "short"),
            "trigger_event": _optional_answer_string(answers, "trigger_event", "short"),
            "process_steps": _list_answer(answers, "process_steps"),
            "systems_involved": _list_answer(answers, "systems_involved"),
            "annual_volume": _optional_int(answers.get("annual_volume")),
            "duration_minutes_per_occurrence": _optional_float(
                answers.get("duration_minutes_per_occurrence")
            ),
            "problem_statement": _optional_answer_string(answers, "problem_statement", "long"),
            "delay_cost_risk_causes": _optional_answer_string(
                answers, "delay_cost_risk_causes", "long"
            ),
            "impact_statement": _optional_answer_string(answers, "impact_statement", "long"),
            "cost_of_inaction": _optional_answer_string(answers, "cost_of_inaction", "medium"),
            "ai_task": _optional_answer_string(answers, "ai_task", "long"),
            "autonomy_level": _optional_answer_string(answers, "autonomy_level", "short"),
            "human_validation_policy": _optional_answer_string(
                answers, "human_validation_policy", "short"
            ),
            "primary_kpi": _optional_answer_string(answers, "primary_kpi", "short"),
            "kpi_target": _optional_answer_string(answers, "kpi_target", "short"),
            "value_hypothesis": _optional_answer_string(answers, "value_hypothesis", "long"),
            "data_sources": _list_answer(answers, "data_sources"),
            "data_availability": _optional_answer_string(answers, "data_availability", "short"),
            "deployment_environment": _optional_answer_string(
                answers, "deployment_environment", "short"
            ),
            "sensitive_data_flag": _optional_answer_string(
                answers, "sensitive_data_flag", "short"
            ),
            "compliance_constraints": _optional_answer_string(
                answers, "compliance_constraints", "long"
            ),
            "risk_hypothesis": _optional_answer_string(answers, "risk_hypothesis", "long"),
            "prohibited_behaviour": _optional_answer_string(
                answers, "prohibited_behaviour", "medium"
            ),
            "missing_knowledge": _optional_answer_string(answers, "missing_knowledge", "long"),
            "existing_problem_statement": _optional_answer_string(
                answers, "problem_statement", "long"
            ),
            "existing_ai_solution": _optional_answer_string(answers, "ai_task", "long"),
            "existing_primary_kpi": _optional_answer_string(answers, "primary_kpi", "short"),
            "existing_value_hypothesis": _optional_answer_string(
                answers, "value_hypothesis", "long"
            ),
            "existing_risk_hypothesis": _optional_answer_string(answers, "risk_hypothesis", "long"),
            "existing_missing_knowledge": _optional_answer_string(
                answers, "missing_knowledge", "long"
            ),
        }
        _reject_sensitive_content(values)
        return KickstartPromptContext.model_validate(values)

    def _audit_attempt(
        self,
        *,
        bundle: AssessmentBundle,
        prompt_context: KickstartPromptContext,
        outcome: str,
        started_at: datetime,
        proposal: KickstartProposal | None = None,
        provider_response: KickstartProviderResponse | None = None,
    ) -> None:
        usage = provider_response.usage if provider_response is not None else None
        self.audit.append(
            context=self.context,
            action="assessment.kickstart_generated",
            entity_type="assessment_version",
            entity_id=str(bundle.assessment.id),
            request_id=self.request_id,
            before={"input": prompt_context.model_dump(mode="json")},
            after=proposal.model_dump(mode="json") if proposal is not None else None,
            metadata={
                "provider": self.provider.provider_name,
                "model": (
                    provider_response.model
                    if provider_response is not None
                    else self.provider.model_name
                ),
                "prompt_template": PROMPT_TEMPLATE_NAME,
                "prompt_hash": _stable_hash(prompt_context.model_dump(mode="json")),
                "output_hash": _stable_hash(proposal.model_dump(mode="json")) if proposal else None,
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
                "latency_ms": int((datetime.now(UTC) - started_at).total_seconds() * 1000),
                "outcome": outcome,
            },
        )

    def _log_provider_failure(self, *, assessment_id: str, code: str) -> None:
        logger.error(
            "Kickstart provider request failed",
            extra={
                "request_id": self.request_id,
                "workspace_id": str(self.context.workspace.id),
                "assessment_id": assessment_id,
                "provider": self.provider.provider_name,
                "model": self.provider.model_name,
                "outcome": code,
            },
        )


class _FakeLlmProvider:
    provider_name = "fake"
    model_name = "fake-kickstart-v1"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def is_configured(self) -> bool:
        return self._settings.app_env == self._settings.app_env.TEST

    def generate_kickstart(
        self,
        request: KickstartPromptRequest,
    ) -> KickstartProviderResponse:
        proposal = self._build_payload(request)
        return KickstartProviderResponse(
            model=self.model_name,
            raw_text=json.dumps(proposal, ensure_ascii=False),
            payload=proposal,
            usage={"prompt_tokens": 64, "completion_tokens": 92, "total_tokens": 156},
        )

    def repair_kickstart(
        self,
        request: KickstartPromptRequest,
        malformed_response: str,
        validation_errors: list[str],
    ) -> KickstartProviderResponse:
        _ = (malformed_response, validation_errors)
        return self.generate_kickstart(request)

    def _build_payload(self, request: KickstartPromptRequest) -> dict[str, object]:
        context = KickstartPromptContext.model_validate_json(request.user_prompt)
        if context.workspace_language.lower().startswith("en"):
            return self._build_en_payload(context)
        return self._build_fr_payload(context)

    def _build_fr_payload(self, context: KickstartPromptContext) -> dict[str, object]:
        department = context.department or "l’équipe métier"
        team_name = context.team_name or department
        return {
            "source": "ai_assisted",
            "problem_statement": (
                f"Le processus cible « {context.target_process} » reste difficile à "
                "standardiser, ce qui rallonge la qualification et multiplie les reprises "
                f"pour {department}."
            ),
            "ai_solution": (
                f"Déployer un assistant IA supervisé pour {context.target_process.lower()} : "
                "il prépare un résumé du dossier, propose la prochaine action et impose "
                "une validation humaine avant toute décision."
            ),
            "kpi_proposals": [
                "Temps moyen de qualification",
                "Taux de dossiers complets au premier passage",
            ],
            "value_hypotheses": [
                f"Réduire les reprises manuelles pour {team_name}.",
                (
                    "Accélérer l’affectation des dossiers prioritaires sans supprimer le "
                    "contrôle humain."
                ),
            ],
            "risks": [
                (
                    "Une synthèse IA inexacte peut orienter la qualification dans la "
                    "mauvaise direction."
                ),
                "La qualité des documents d’entrée peut limiter la fiabilité des recommandations.",
            ],
            "missing_info": [
                "La baseline actuelle du délai de qualification reste à confirmer.",
                (
                    "Les règles métier bloquantes à formaliser pour la validation humaine "
                    "manquent encore."
                ),
            ],
        }

    def _build_en_payload(self, context: KickstartPromptContext) -> dict[str, object]:
        department = context.department or "the business team"
        team_name = context.team_name or department
        return {
            "source": "ai_assisted",
            "problem_statement": (
                f"The target process '{context.target_process}' remains hard to standardize, "
                f"which slows qualification and increases rework for {department}."
            ),
            "ai_solution": (
                f"Deploy a supervised AI assistant for {context.target_process.lower()}: "
                "it prepares a case summary, recommends the next action, and requires "
                "human validation before any decision."
            ),
            "kpi_proposals": [
                "Average qualification time",
                "First-pass complete-case rate",
            ],
            "value_hypotheses": [
                f"Reduce manual rework for {team_name}.",
                "Speed up prioritised case assignment without removing human oversight.",
            ],
            "risks": [
                "An inaccurate AI summary could steer qualification in the wrong direction.",
                "Input document quality may limit recommendation reliability.",
            ],
            "missing_info": [
                "The current qualification lead-time baseline still needs confirmation.",
                "Blocking business rules for human validation are not yet documented.",
            ],
        }


class _UnavailableLlmProvider:
    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        self.model_name = "unconfigured"

    def is_configured(self) -> bool:
        return False

    def generate_kickstart(
        self,
        request: KickstartPromptRequest,
    ) -> KickstartProviderResponse:
        _ = request
        raise LlmProviderConfigurationError(
            "The configured LLM provider is reserved for tests and unavailable at runtime."
        )

    def repair_kickstart(
        self,
        request: KickstartPromptRequest,
        malformed_response: str,
        validation_errors: list[str],
    ) -> KickstartProviderResponse:
        _ = (request, malformed_response, validation_errors, KICKSTART_REPAIR_PROMPT)
        raise LlmProviderConfigurationError(
            "The configured LLM provider is reserved for tests and unavailable at runtime."
        )


def _build_provider(settings: Settings) -> LlmProvider:
    if settings.llm_provider == LlmProviderKind.OPENAI:
        return OpenAIProvider(settings)
    if settings.llm_provider == LlmProviderKind.AZURE_OPENAI:
        return AzureOpenAIProvider(settings)
    if settings.llm_provider == LlmProviderKind.ANTHROPIC:
        return AnthropicProvider(settings)
    if settings.llm_provider == LlmProviderKind.FAKE:
        return _FakeLlmProvider(settings)
    return _UnavailableLlmProvider(str(settings.llm_provider))


def _window_start(now: datetime, window_seconds: int) -> datetime:
    unix_timestamp = int(now.timestamp())
    start_timestamp = unix_timestamp - (unix_timestamp % window_seconds)
    return datetime.fromtimestamp(start_timestamp, tz=UTC)


def _stable_hash(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _bound_string(value: str, bucket: str) -> str:
    return value.strip()[: FIELD_LENGTH_LIMITS[bucket]]


def _optional_bound_string(value: str | None, bucket: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized[: FIELD_LENGTH_LIMITS[bucket]] if normalized else None


def _answer_value(answer: Answer | None) -> Any:
    if answer is None:
        return None
    return answer.value_data_json


def _required_answer_string(answers: dict[str, Answer], key: str, bucket: str) -> str:
    value = _optional_answer_string(answers, key, bucket)
    if value:
        return value
    raise AppError(
        status_code=422,
        title="Validation Error",
        detail=(
            "L’assistance IA requiert un résumé non sensible du processus cible et du problème "
            "avant génération."
        ),
    )


def _optional_answer_string(answers: dict[str, Answer], key: str, bucket: str) -> str | None:
    value = _answer_value(answers.get(key))
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized[: FIELD_LENGTH_LIMITS[bucket]] if normalized else None


def _list_answer(answers: dict[str, Answer], key: str) -> list[str]:
    value = _answer_value(answers.get(key))
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for entry in value:
        if isinstance(entry, str):
            normalized = entry.strip()
            if normalized:
                result.append(normalized[: FIELD_LENGTH_LIMITS["short"]])
        if len(result) >= 8:
            break
    return result


def _optional_int(answer: Answer | None) -> int | None:
    value = _answer_value(answer)
    return value if isinstance(value, int) and value > 0 else None


def _optional_float(answer: Answer | None) -> float | None:
    value = _answer_value(answer)
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return None


def _reject_sensitive_content(values: dict[str, Any]) -> None:
    for value in values.values():
        if isinstance(value, str):
            _assert_safe_text(value)
            continue
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, str):
                    _assert_safe_text(entry)


def _assert_safe_text(value: str) -> None:
    for pattern in PII_SECRET_PATTERNS:
        if pattern.search(value):
            raise AppError(
                status_code=422,
                title="Validation Error",
                detail=(
                    "L’assistance IA refuse les résumés contenant des secrets ou des données "
                    "personnelles. Remplacez-les par un résumé métier non sensible."
                ),
            )
