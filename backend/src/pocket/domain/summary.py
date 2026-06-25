"""Daily summary assembly: calendar + tasks + overdue + completion prompts.

Read-only. Email is included only when explicitly requested (privacy discipline).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from pocket.core.config import Settings, get_settings
from pocket.db.enums import TaskPriority, TaskStatus
from pocket.db.models import Task
from pocket.domain import tasks as task_logic
from pocket.integrations import registry


def build_daily_summary(db: Session, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    today_iso = now.date().isoformat()

    active = db.query(Task).filter(Task.status.in_([TaskStatus.active, TaskStatus.scheduled])).all()
    overdue = [t for t in active if task_logic.is_overdue(t, now)]

    calendar = registry.get_calendar(settings)
    busy = calendar.free_busy(today_iso)
    events = [{"start": s.start, "end": s.end, "busy": True} for s in busy]

    completion_prompts = [
        f"Did you finish '{t.title}'?"
        for t in active
        if task_logic.is_overdue(t, now) or t.priority in (TaskPriority.high, TaskPriority.urgent)
    ]

    spoken = _spoken_text(
        events_count=len(events), task_count=len(active), overdue_count=len(overdue)
    )

    return {
        "spoken_text": spoken,
        "events": events,
        "tasks": active,
        "overdue": overdue,
        "completion_prompts": completion_prompts,
    }


def _spoken_text(events_count: int, task_count: int, overdue_count: int) -> str:
    parts = [f"You have {events_count} calendar item(s) today and {task_count} active task(s)."]
    if overdue_count:
        parts.append(f"{overdue_count} are overdue and not marked done.")
    else:
        parts.append("Nothing is overdue.")
    return " ".join(parts)
