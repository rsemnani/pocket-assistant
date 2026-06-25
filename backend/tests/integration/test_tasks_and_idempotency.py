"""Task CRUD, snooze/done, idempotency, and the reminder scan."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from pocket.db.enums import TaskPriority, TaskStatus
from pocket.db.models import Task
from pocket.workers.reminders import run_scan


def test_task_crud_and_done(client: TestClient, auth: dict):
    created = client.post("/v1/tasks", json={"title": "buy milk"}, headers=auth)
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert created.json()["status"] == "active"

    done = client.post(f"/v1/tasks/{task_id}/done", headers=auth)
    assert done.status_code == 200
    assert done.json()["status"] == "done"
    assert done.json()["completed_at"] is not None


def test_snooze(client: TestClient, auth: dict):
    created = client.post("/v1/tasks", json={"title": "stretch"}, headers=auth)
    task_id = created.json()["id"]
    until = (datetime.now(UTC) + timedelta(hours=3)).isoformat()
    resp = client.post(f"/v1/tasks/{task_id}/snooze", json={"snooze_until": until}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "snoozed"


def test_capture_idempotency_key_dedup(client: TestClient, auth: dict):
    headers = {**auth, "Idempotency-Key": "abc-123"}
    body = {"transcript": "hello world"}
    first = client.post("/v1/captures", json=body, headers=headers)
    second = client.post("/v1/captures", json=body, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_idempotency_key_conflict_on_different_body(client: TestClient, auth: dict):
    headers = {**auth, "Idempotency-Key": "dup-key"}
    client.post("/v1/captures", json={"transcript": "one"}, headers=headers)
    conflict = client.post("/v1/captures", json={"transcript": "two"}, headers=headers)
    assert conflict.status_code == 409


def test_reminder_scan_escalates_overdue(client: TestClient, auth: dict, session_factory):
    # Seed an overdue normal task directly, then run the scan.
    db = session_factory()
    task = Task(
        title="overdue thing",
        status=TaskStatus.active,
        priority=TaskPriority.normal,
        due_at=datetime.now(UTC) - timedelta(days=2),
        tags=[],
    )
    db.add(task)
    db.commit()
    task_id = task.id

    result = run_scan(db)
    db.commit()
    assert str(task_id) in result.escalated

    refreshed = db.get(Task, task_id)
    assert refreshed.priority == TaskPriority.high
    db.close()


def test_audit_log_records_events(client: TestClient, auth: dict):
    client.post("/v1/tasks", json={"title": "audited task"}, headers=auth)
    audit = client.get("/v1/audit", headers=auth)
    assert audit.status_code == 200
    events = {e["event"] for e in audit.json()}
    assert "TASK_CREATED" in events
    assert "DEVICE_REGISTERED" in events
