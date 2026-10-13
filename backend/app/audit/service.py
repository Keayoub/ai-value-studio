from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.audit.models import AuditEvent
from app.security.tenancy import WorkspaceContext
from sqlmodel import Session


def _canonicalize_audit_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize_audit_value(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_canonicalize_audit_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_canonicalize_audit_value(item) for item in value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.isoformat()
        return value.astimezone(UTC).replace(tzinfo=None).isoformat()
    if isinstance(value, str) and "T" in value:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value
        return _canonicalize_audit_value(parsed)
    return value


def hash_audit_snapshot(snapshot: dict | None) -> str | None:
    if snapshot is None:
        return None
    canonical_json = json.dumps(
        _canonicalize_audit_value(snapshot),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(
        self,
        *,
        context: WorkspaceContext,
        action: str,
        entity_type: str,
        entity_id: str,
        request_id: str,
        before: dict | None = None,
        after: dict | None = None,
        metadata: dict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            workspace_id=context.workspace.id,
            actor_subject_id=context.membership.identity_subject_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=request_id,
            before_hash=hash_audit_snapshot(before),
            after_hash=hash_audit_snapshot(after),
            metadata_json=metadata,
        )
        self.session.add(event)
        return event
