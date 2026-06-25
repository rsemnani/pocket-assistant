"""Audit logging helper. Writes append-only, redacted-summary audit rows."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from pocket.db.base import utcnow
from pocket.db.enums import AuditActor
from pocket.db.models import AuditLog


def record(
    db: Session,
    *,
    actor: AuditActor,
    event: str,
    summary: str,
    capture_id: uuid.UUID | None = None,
    action_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
    detail_ref: uuid.UUID | None = None,
) -> AuditLog:
    """Append an audit entry. `summary` must be redacted (no raw transcript/email bodies)."""
    entry = AuditLog(
        ts=utcnow(),
        actor=actor,
        event=event,
        summary=summary,
        capture_id=capture_id,
        action_id=action_id,
        task_id=task_id,
        detail_ref=detail_ref,
    )
    db.add(entry)
    db.flush()
    return entry
