"""Task endpoints: list, create, update, snooze, mark done."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from pocket.api.deps import DbDep, DeviceDep
from pocket.core.errors import NotFoundError
from pocket.db.enums import AuditActor, TaskPriority, TaskStatus
from pocket.db.models import Task
from pocket.domain import audit
from pocket.domain import tasks as task_logic
from pocket.schemas.api import (
    SnoozeRequest,
    TaskCreateRequest,
    TaskResponse,
    TaskUpdateRequest,
)

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])


def _get_task(db: DbDep, task_id: uuid.UUID) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise NotFoundError("task not found")
    return task


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    db: DbDep,
    device: DeviceDep,
    status: TaskStatus | None = Query(default=None),
    priority: TaskPriority | None = Query(default=None),
) -> list[Task]:
    query = db.query(Task)
    if status is not None:
        query = query.filter(Task.status == status)
    if priority is not None:
        query = query.filter(Task.priority == priority)
    return query.order_by(Task.created_at.desc()).all()


@router.post("", response_model=TaskResponse, status_code=201)
def create_task(body: TaskCreateRequest, db: DbDep, device: DeviceDep) -> Task:
    task = Task(
        title=body.title,
        notes=body.notes,
        priority=body.priority,
        due_at=body.due_at,
        tags=body.tags,
    )
    db.add(task)
    db.flush()
    audit.record(
        db,
        actor=AuditActor.user,
        event="TASK_CREATED",
        summary=f"priority={body.priority.value}",
        task_id=task.id,
    )
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(task_id: uuid.UUID, body: TaskUpdateRequest, db: DbDep, device: DeviceDep) -> Task:
    task = _get_task(db, task_id)
    if body.title is not None:
        task.title = body.title
    if body.notes is not None:
        task.notes = body.notes
    if body.priority is not None:
        task.priority = body.priority
    if body.due_at is not None:
        task.due_at = body.due_at
    if body.status is not None:
        if body.status == TaskStatus.done:
            task_logic.mark_done(task)
        else:
            task.status = body.status
    db.flush()
    return task


@router.post("/{task_id}/snooze", response_model=TaskResponse)
def snooze_task(task_id: uuid.UUID, body: SnoozeRequest, db: DbDep, device: DeviceDep) -> Task:
    task = _get_task(db, task_id)
    task_logic.snooze(task, body.snooze_until)
    db.flush()
    audit.record(
        db, actor=AuditActor.user, event="TASK_SNOOZED", summary="snoozed", task_id=task.id
    )
    return task


@router.post("/{task_id}/done", response_model=TaskResponse)
def mark_done(task_id: uuid.UUID, db: DbDep, device: DeviceDep) -> Task:
    """Explicit completion only."""
    task = _get_task(db, task_id)
    task_logic.mark_done(task)
    db.flush()
    audit.record(
        db, actor=AuditActor.user, event="TASK_DONE", summary="marked done", task_id=task.id
    )
    return task
