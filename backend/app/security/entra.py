from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from urllib.request import urlopen


@dataclass(slots=True)
class JwksCacheEntry:
    expires_at: float
    keys: dict[str, dict]


class JwksCache:
    def __init__(self, jwks_url: str, ttl_seconds: int) -> None:
        self._jwks_url = jwks_url
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._entry: JwksCacheEntry | None = None

    def get_key(self, kid: str) -> dict | None:
        keys = self._get_keys()
        return keys.get(kid)

    def _get_keys(self) -> dict[str, dict]:
        now = time.time()
        with self._lock:
            if self._entry and self._entry.expires_at > now:
                return self._entry.keys

            with urlopen(self._jwks_url, timeout=5) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))

            keys = {
                key["kid"]: key
                for key in payload.get("keys", [])
                if isinstance(key, dict) and key.get("kid")
            }
            self._entry = JwksCacheEntry(expires_at=now + self._ttl_seconds, keys=keys)
            return keys
