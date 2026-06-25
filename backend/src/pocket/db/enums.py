"""Shared enumerations used by models and Pydantic schemas."""

from __future__ import annotations

from enum import Enum


class DeviceStatus(str, Enum):
    active = "active"
    revoked = "revoked"


class CaptureStatus(str, Enum):
    received = "received"
    interpreting = "interpreting"
    proposed = "proposed"
    executed = "executed"
    cancelled = "cancelled"
    error = "error"


class TranscriptionSource(str, Enum):
    device = "device"
    server = "server"


class TaskStatus(str, Enum):
    active = "active"
    scheduled = "scheduled"
    snoozed = "snoozed"
    done = "done"
    archived = "archived"


class TaskPriority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class ActionType(str, Enum):
    create_task = "create_task"
    update_task = "update_task"
    create_note = "create_note"
    propose_event = "propose_event"
    email_search = "email_search"
    email_draft = "email_draft"
    create_github_issue = "create_github_issue"
    prepare_cc_job = "prepare_cc_job"
    invoke_cc_job = "invoke_cc_job"
    daily_summary = "daily_summary"
    clarify = "clarify"


class Sensitivity(str, Enum):
    normal = "normal"
    approval = "approval"
    pin_required = "pin_required"


class ActionStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    executing = "executing"
    executed = "executed"
    failed = "failed"


class ReminderCadence(str, Enum):
    once = "once"
    hourly = "hourly"
    daily = "daily"


class MediaKind(str, Enum):
    audio = "audio"
    ics = "ics"
    attachment = "attachment"
    llm_blob = "llm_blob"
    export = "export"


class AuditActor(str, Enum):
    device = "device"
    worker = "worker"
    llm = "llm"
    system = "system"
    user = "user"
