"""Task lifecycle logic: creation, escalation, snooze, completion, nag eligibility.

Pure-ish functions operating on Task instances so they are easy to unit test. Completion is
ALWAYS explicit — nothing here auto-marks a task done.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pocket.db.enums import ReminderCadence, TaskPriority, TaskStatus
from pocket.db.models import Task


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


def is_overdue(task: Task, now: datetime | None = None) -> bool:
    if task.due_at is None or task.status in (TaskStatus.done, TaskStatus.archived):
        return False
    return task.due_at < _now(now)


def escalate_if_overdue(task: Task, now: datetime | None = None) -> bool:
    """Raise an overdue task to at least HIGH priority. Returns True if changed.

    Urgent stays urgent. Snoozed tasks are not escalated until their snooze elapses.
    """
    if task.status == TaskStatus.snoozed and task.snooze_until and task.snooze_until > _now(now):
        return False
    if not is_overdue(task, now):
        return False
    if task.priority in (TaskPriority.low, TaskPriority.normal):
        task.priority = TaskPriority.high
        return True
    return False


def snooze(task: Task, until: datetime) -> None:
    task.status = TaskStatus.snoozed
    task.snooze_until = until


def mark_done(task: Task, now: datetime | None = None) -> None:
    """Explicit completion only — callers invoke this in response to a user instruction."""
    task.status = TaskStatus.done
    task.completed_at = _now(now)


def nag_due(task: Task, now: datetime | None = None) -> bool:
    """Whether a nag/reminder should fire now, honoring snooze and cadence throttling.

    - urgent: hourly
    - high + overdue: daily
    - others: no nag
    """
    now_ = _now(now)
    if task.status in (TaskStatus.done, TaskStatus.archived):
        return False
    if task.status == TaskStatus.snoozed and task.snooze_until and task.snooze_until > now_:
        return False

    if task.priority == TaskPriority.urgent:
        cadence = timedelta(hours=1)
    elif task.priority == TaskPriority.high and is_overdue(task, now_):
        cadence = timedelta(days=1)
    else:
        return False

    if task.last_nag_at is None:
        return True
    return (now_ - task.last_nag_at) >= cadence


def cadence_for(task: Task) -> ReminderCadence:
    if task.priority == TaskPriority.urgent:
        return ReminderCadence.hourly
    if task.priority == TaskPriority.high:
        return ReminderCadence.daily
    return ReminderCadence.once
