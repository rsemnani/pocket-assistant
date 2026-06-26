"""Request/response schemas for the HTTP API. Input validation lives here."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pocket.db.enums import (
    ActionStatus,
    ActionType,
    CaptureStatus,
    Sensitivity,
    TaskPriority,
    TaskStatus,
    TranscriptionSource,
)


# ── Devices / sessions ─────────────────────────────────────────────────────────
class DeviceRegisterRequest(BaseModel):
    registration_code: str = Field(min_length=4, max_length=128)
    name: str = Field(default="device", max_length=120)


class DeviceRegisterResponse(BaseModel):
    device_id: uuid.UUID
    device_token: str = Field(description="Returned exactly once; store securely on device.")


class SessionPinRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=32)


class SessionPinResponse(BaseModel):
    session_token: str
    expires_at: datetime


# ── Captures ───────────────────────────────────────────────────────────────────
class CaptureCreateRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=10000)
    captured_at: datetime | None = None
    transcription_source: TranscriptionSource = TranscriptionSource.device


class TranscriptUpdateRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=10000)


class CaptureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: CaptureStatus
    transcript_edited: str | None = None


# ── Proposals ──────────────────────────────────────────────────────────────────
class ProposedActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: ActionType
    explanation: str
    payload: dict[str, Any]
    sensitivity: Sensitivity
    status: ActionStatus


class ProposalListResponse(BaseModel):
    capture_id: uuid.UUID
    intent: str
    actions: list[ProposedActionResponse]


class ApproveResponse(BaseModel):
    action_id: uuid.UUID
    status: ActionStatus
    external_ref: dict[str, Any] | None = None


# ── Tasks ──────────────────────────────────────────────────────────────────────
class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    notes: str | None = None
    priority: TaskPriority = TaskPriority.normal
    due_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)


class TaskUpdateRequest(BaseModel):
    title: str | None = None
    notes: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None


class SnoozeRequest(BaseModel):
    snooze_until: datetime


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    notes: str | None
    status: TaskStatus
    priority: TaskPriority
    due_at: datetime | None
    tags: list[str]
    snooze_until: datetime | None
    completed_at: datetime | None


# ── Daily summary ──────────────────────────────────────────────────────────────
class DailySummaryResponse(BaseModel):
    spoken_text: str
    events: list[dict[str, Any]]
    tasks: list[TaskResponse]
    overdue: list[TaskResponse]
    completion_prompts: list[str]


# ── Audit ──────────────────────────────────────────────────────────────────────
class AuditEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    ts: datetime
    actor: str
    event: str
    summary: str
