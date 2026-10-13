from __future__ import annotations

import json

from app.config import Settings
from app.llm.contracts import (
    LlmProvider,
    LlmProviderConfigurationError,
    LlmProviderRateLimitError,
    LlmProviderResponseError,
    LlmProviderTimeoutError,
)
from app.llm.prompts.kickstart_fr import KICKSTART_REPAIR_PROMPT
from app.llm.schemas import KickstartPromptRequest, KickstartProviderResponse, LlmTokenUsage


class AnthropicProvider(LlmProvider):
    provider_name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.model_name = settings.anthropic_model
        self._client = None

    def is_configured(self) -> bool:
        return bool(self._settings.anthropic_api_key)

    def generate_kickstart(
        self,
        request: KickstartPromptRequest,
    ) -> KickstartProviderResponse:
        return self._create_completion(request.system_prompt, request.user_prompt)

    def repair_kickstart(
        self,
        request: KickstartPromptRequest,
        malformed_response: str,
        validation_errors: list[str],
    ) -> KickstartProviderResponse:
        repair_prompt = (
            f"{request.user_prompt}\n\nRéponse invalide précédente :\n{malformed_response}\n\n"
            f"Erreurs de validation : {json.dumps(validation_errors, ensure_ascii=False)}\n\n"
            f"{KICKSTART_REPAIR_PROMPT}"
        )
        return self._create_completion(request.system_prompt, repair_prompt)

    @property
    def client(self):
        if not self.is_configured():
            raise LlmProviderConfigurationError()
        if self._client is None:
            from anthropic import Anthropic

            self._client = Anthropic(
                api_key=self._settings.anthropic_api_key,
                timeout=self._settings.llm_request_timeout_seconds,
            )
        return self._client

    def _create_completion(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> KickstartProviderResponse:
        try:
            response = self.client.messages.create(
                model=self.model_name,
                system=system_prompt,
                temperature=0,
                max_tokens=1200,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:
            raise _map_anthropic_error(exc) from exc

        raw_text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
        if not raw_text:
            raise LlmProviderResponseError()
        return KickstartProviderResponse(
            model=self.model_name,
            raw_text=raw_text,
            payload=_load_json(raw_text),
            usage=LlmTokenUsage(
                prompt_tokens=getattr(response.usage, "input_tokens", 0),
                completion_tokens=getattr(response.usage, "output_tokens", 0),
                total_tokens=getattr(response.usage, "input_tokens", 0)
                + getattr(response.usage, "output_tokens", 0),
            )
            if getattr(response, "usage", None) is not None
            else None,
        )


def _load_json(raw_text: str) -> dict[str, object] | None:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _map_anthropic_error(exc: Exception) -> Exception:
    from anthropic import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

    if isinstance(exc, (APITimeoutError, APIConnectionError)):
        return LlmProviderTimeoutError()
    if isinstance(exc, RateLimitError):
        return LlmProviderRateLimitError()
    if isinstance(exc, APIStatusError):
        if exc.status_code == 429:
            return LlmProviderRateLimitError()
        return LlmProviderResponseError()
    return LlmProviderResponseError()
