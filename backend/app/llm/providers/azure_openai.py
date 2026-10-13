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
from app.llm.schemas import KickstartPromptRequest, KickstartProviderResponse, LlmTokenUsage


class AzureOpenAIProvider(LlmProvider):
    provider_name = "azure_openai"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.model_name = settings.azure_openai_deployment_name or "azure-openai"
        self._client = None

    def is_configured(self) -> bool:
        return bool(
            self._settings.azure_openai_api_key
            and self._settings.azure_openai_endpoint
            and self._settings.azure_openai_deployment_name
        )

    def generate_kickstart(
        self,
        request: KickstartPromptRequest,
    ) -> KickstartProviderResponse:
        return self._create_completion(request.system_prompt, request.user_prompt, request)

    def repair_kickstart(
        self,
        request: KickstartPromptRequest,
        malformed_response: str,
        validation_errors: list[str],
    ) -> KickstartProviderResponse:
        repair_prompt = (
            f"{request.user_prompt}\n\nRéponse invalide précédente :\n{malformed_response}\n\n"
            f"Erreurs de validation : {json.dumps(validation_errors, ensure_ascii=False)}"
        )
        return self._create_completion(request.system_prompt, repair_prompt, request)

    @property
    def client(self):
        if not self.is_configured():
            raise LlmProviderConfigurationError()
        if self._client is None:
            from openai import AzureOpenAI

            self._client = AzureOpenAI(
                api_key=self._settings.azure_openai_api_key,
                azure_endpoint=self._settings.azure_openai_endpoint,
                api_version=self._settings.azure_openai_api_version,
                timeout=self._settings.llm_request_timeout_seconds,
            )
        return self._client

    def _create_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        request: KickstartPromptRequest,
    ) -> KickstartProviderResponse:
        try:
            response = self.client.chat.completions.create(
                model=self._settings.azure_openai_deployment_name,
                temperature=0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "kickstart_proposal",
                        "strict": True,
                        "schema": request.response_schema,
                    },
                },
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:
            raise _map_azure_error(exc) from exc

        message = response.choices[0].message
        raw_text = message.content or ""
        if not raw_text:
            raise LlmProviderResponseError()
        usage = response.usage
        return KickstartProviderResponse(
            model=self.model_name,
            raw_text=raw_text,
            payload=_load_json(raw_text),
            usage=LlmTokenUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            )
            if usage is not None
            else None,
        )


def _load_json(raw_text: str) -> dict[str, object] | None:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _map_azure_error(exc: Exception) -> Exception:
    from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

    if isinstance(exc, (APITimeoutError, APIConnectionError)):
        return LlmProviderTimeoutError()
    if isinstance(exc, RateLimitError):
        return LlmProviderRateLimitError()
    if isinstance(exc, APIStatusError):
        if exc.status_code == 429:
            return LlmProviderRateLimitError()
        return LlmProviderResponseError()
    return LlmProviderResponseError()
