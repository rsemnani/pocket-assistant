"""Unit tests for task escalation, snooze, completion, and nag logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pocket.db.enums import TaskPriority, TaskStatus
from pocket.db.models import Task
from pocket.domain import tasks as task_logic

NOW = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)


def _task(**kw) -> Task:
    defaults = {
        "title": "t",
        "status": TaskStatus.active,
        "priority": TaskPriority.normal,
        "tags": [],
    }
    defaults.update(kw)
    return Task(**defaults)


def test_overdue_detection():
    assert task_logic.is_overdue(_task(due_at=NOW - timedelta(hours=1)), NOW)
    assert not task_logic.is_overdue(_task(due_at=NOW + timedelta(hours=1)), NOW)
    assert not task_logic.is_overdue(_task(due_at=None), NOW)


def test_overdue_escalates_normal_to_high():
    task = _task(priority=TaskPriority.normal, due_at=NOW - timedelta(days=1))
    assert task_logic.escalate_if_overdue(task, NOW) is True
    assert task.priority == TaskPriority.high


def test_done_task_not_escalated():
    task = _task(
        status=TaskStatus.done, priority=TaskPriority.normal, due_at=NOW - timedelta(days=1)
    )
    assert task_logic.escalate_if_overdue(task, NOW) is False


def test_snoozed_task_not_escalated_until_window_elapses():
    task = _task(
        status=TaskStatus.snoozed,
        priority=TaskPriority.normal,
        due_at=NOW - timedelta(days=1),
        snooze_until=NOW + timedelta(hours=2),
    )
    assert task_logic.escalate_if_overdue(task, NOW) is False


def test_mark_done_is_explicit_and_sets_completed_at():
    task = _task()
    task_logic.mark_done(task, NOW)
    assert task.status == TaskStatus.done
    assert task.completed_at == NOW


def test_urgent_nags_hourly():
    task = _task(priority=TaskPriority.urgent, last_nag_at=NOW - timedelta(minutes=30))
    assert task_logic.nag_due(task, NOW) is False
    task.last_nag_at = NOW - timedelta(hours=2)
    assert task_logic.nag_due(task, NOW) is True


def test_high_overdue_nags_daily():
    task = _task(priority=TaskPriority.high, due_at=NOW - timedelta(days=3), last_nag_at=None)
    assert task_logic.nag_due(task, NOW) is True
    task.last_nag_at = NOW - timedelta(hours=2)
    assert task_logic.nag_due(task, NOW) is False


def test_normal_priority_does_not_nag():
    task = _task(priority=TaskPriority.normal, due_at=NOW - timedelta(days=1))
    assert task_logic.nag_due(task, NOW) is False
