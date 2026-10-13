from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from json import JSONDecodeError
from urllib.request import urlopen


@dataclass(slots=True)
class JwksCacheEntry:
    expires_at: float
    keys: dict[str, dict]


@dataclass(slots=True)
class JwksFailureEntry:
    retry_at: float


class JwksFetchError(RuntimeError):
    pass


class JwksCache:
    def __init__(
        self,
        jwks_url: str,
        ttl_seconds: int,
        *,
        failure_retry_seconds: int | None = None,
    ) -> None:
        self._jwks_url = jwks_url
        self._ttl_seconds = ttl_seconds
        self._failure_retry_seconds = max(
            1,
            failure_retry_seconds if failure_retry_seconds is not None else min(ttl_seconds, 30),
        )
        self._lock = threading.Lock()
        self._entry: JwksCacheEntry | None = None
        self._failure: JwksFailureEntry | None = None

    def get_key(self, kid: str) -> dict | None:
        keys = self._get_keys()
        return keys.get(kid)

    def _get_keys(self) -> dict[str, dict]:
        now = time.time()
        with self._lock:
            if self._entry and self._entry.expires_at > now:
                return self._entry.keys

            if self._failure and self._failure.retry_at > now:
                raise JwksFetchError("JWKS refresh is temporarily unavailable.")

            try:
                payload = self._fetch_payload()
                keys = self._extract_keys(payload)
            except JwksFetchError:
                self._failure = JwksFailureEntry(retry_at=now + self._failure_retry_seconds)
                raise

            self._failure = None
            self._entry = JwksCacheEntry(expires_at=now + self._ttl_seconds, keys=keys)
            return keys

    def _fetch_payload(self) -> dict[str, object]:
        try:
            with urlopen(self._jwks_url, timeout=5) as response:  # noqa: S310
                raw_payload = response.read().decode("utf-8")
        except (OSError, TimeoutError, UnicodeDecodeError) as exc:
            raise JwksFetchError("Unable to retrieve JWKS.") from exc

        try:
            payload = json.loads(raw_payload)
        except JSONDecodeError as exc:
            raise JwksFetchError("JWKS response was not valid JSON.") from exc

        if not isinstance(payload, dict):
            raise JwksFetchError("JWKS response must be a JSON object.")
        return payload

    def _extract_keys(self, payload: dict[str, object]) -> dict[str, dict]:
        raw_keys = payload.get("keys")
        if not isinstance(raw_keys, list):
            raise JwksFetchError("JWKS response keys must be a list.")

        return {
            key["kid"]: key
            for key in raw_keys
            if isinstance(key, dict) and isinstance(key.get("kid"), str) and key["kid"]
        }
