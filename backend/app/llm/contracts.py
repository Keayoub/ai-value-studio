from __future__ import annotations

from typing import Protocol

from app.llm.schemas import KickstartPromptRequest, KickstartProviderResponse


class LlmProviderError(Exception):
    def __init__(self, message: str, *, code: str, retryable: bool) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(message)


class LlmProviderTimeoutError(LlmProviderError):
    def __init__(self, message: str = "The provider did not answer before the timeout.") -> None:
        super().__init__(message, code="timeout", retryable=True)


class LlmProviderRateLimitError(LlmProviderError):
    def __init__(self, message: str = "The provider rate limit has been reached.") -> None:
        super().__init__(message, code="provider-rate-limit", retryable=True)


class LlmProviderResponseError(LlmProviderError):
    def __init__(self, message: str = "The provider returned an invalid response.") -> None:
        super().__init__(message, code="invalid-response", retryable=False)


class LlmProviderConfigurationError(LlmProviderError):
    def __init__(self, message: str = "The provider is not configured.") -> None:
        super().__init__(message, code="provider-unconfigured", retryable=False)


class LlmProvider(Protocol):
    provider_name: str
    model_name: str

    def is_configured(self) -> bool: ...

    def generate_kickstart(
        self,
        request: KickstartPromptRequest,
    ) -> KickstartProviderResponse: ...

    def repair_kickstart(
        self,
        request: KickstartPromptRequest,
        malformed_response: str,
        validation_errors: list[str],
    ) -> KickstartProviderResponse: ...
