"""Reminder/escalation scan.

Periodically: escalate overdue tasks to high priority and determine which tasks are due for
a nag. This function is pure w.r.t. the DB session passed in, so it is easy to test and can
be driven by a scheduler (cron/RQ-beat) in later phases.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from pocket.db.base import utcnow
from pocket.db.enums import AuditActor, TaskStatus
from pocket.db.models import Task
from pocket.domain import audit
from pocket.domain import tasks as task_logic


@dataclass
class ScanResult:
    escalated: list[str]
    nags: list[str]


def run_scan(db: Session, now: datetime | None = None) -> ScanResult:
    now = now or datetime.now(UTC)
    escalated: list[str] = []
    nags: list[str] = []

    open_tasks = (
        db.query(Task)
        .filter(Task.status.in_([TaskStatus.active, TaskStatus.scheduled, TaskStatus.snoozed]))
        .all()
    )
    for task in open_tasks:
        if task_logic.escalate_if_overdue(task, now):
            escalated.append(str(task.id))
            audit.record(
                db,
                actor=AuditActor.system,
                event="TASK_ESCALATED",
                summary=f"-> {task.priority.value} (overdue)",
                task_id=task.id,
            )
        if task_logic.nag_due(task, now):
            nags.append(str(task.id))
            task.last_nag_at = utcnow()

    db.flush()
    return ScanResult(escalated=escalated, nags=nags)
