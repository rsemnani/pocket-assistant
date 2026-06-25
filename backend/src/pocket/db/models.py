"""SQLAlchemy ORM models. Operational data only — no raw audio bytes live here.

Portable column types (GUID / json_column) keep these models compatible with both Postgres
(production) and SQLite (tests). Enums are stored as their string values.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pocket.db import enums
from pocket.db.base import Base, Timestamps, UUIDPrimaryKey
from pocket.db.types import GUID, json_column


def _enum(enum_cls: type, name: str) -> SAEnum:
    return SAEnum(enum_cls, name=name, native_enum=False, validate_strings=True)


class Device(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "devices"

    name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[enums.DeviceStatus] = mapped_column(
        _enum(enums.DeviceStatus, "device_status"), default=enums.DeviceStatus.active
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Session(UUIDPrimaryKey, Timestamps, Base):
    """A PIN-unlocked window granting access to pin_required actions."""

    __tablename__ = "sessions"

    device_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("devices.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    pin_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MediaObject(UUIDPrimaryKey, Timestamps, Base):
    """Metadata for a binary stored on the filesystem (bytes are NOT in the DB)."""

    __tablename__ = "media_objects"

    kind: Mapped[enums.MediaKind] = mapped_column(_enum(enums.MediaKind, "media_kind"))
    path: Mapped[str] = mapped_column(String(512))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    retention_class: Mapped[str] = mapped_column(String(32), default="derived")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Capture(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "captures"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_captures_idempotency_key"),)

    device_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("devices.id"), index=True)
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("media_objects.id"), nullable=True
    )
    transcript_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_edited: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcription_source: Mapped[enums.TranscriptionSource] = mapped_column(
        _enum(enums.TranscriptionSource, "transcription_source"),
        default=enums.TranscriptionSource.device,
    )
    status: Mapped[enums.CaptureStatus] = mapped_column(
        _enum(enums.CaptureStatus, "capture_status"), default=enums.CaptureStatus.received
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    interpretations: Mapped[list[Interpretation]] = relationship(
        back_populates="capture", cascade="all, delete-orphan"
    )


class Interpretation(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "interpretations"

    capture_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("captures.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intent: Mapped[str] = mapped_column(String(64))
    raw_blob_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("media_objects.id"), nullable=True
    )
    validation_status: Mapped[str] = mapped_column(String(16), default="valid")

    capture: Mapped[Capture] = relationship(back_populates="interpretations")
    actions: Mapped[list[ProposedAction]] = relationship(
        back_populates="interpretation", cascade="all, delete-orphan"
    )


class ProposedAction(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "proposed_actions"

    interpretation_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("interpretations.id"), index=True
    )
    type: Mapped[enums.ActionType] = mapped_column(_enum(enums.ActionType, "action_type"))
    payload: Mapped[dict[str, Any]] = mapped_column(json_column(), default=dict)
    explanation: Mapped[str] = mapped_column(Text)
    sensitivity: Mapped[enums.Sensitivity] = mapped_column(
        _enum(enums.Sensitivity, "sensitivity"), default=enums.Sensitivity.approval
    )
    status: Mapped[enums.ActionStatus] = mapped_column(
        _enum(enums.ActionStatus, "action_status"), default=enums.ActionStatus.pending
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_ref: Mapped[dict[str, Any] | None] = mapped_column(json_column(), nullable=True)

    interpretation: Mapped[Interpretation] = relationship(back_populates="actions")


class Task(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[enums.TaskStatus] = mapped_column(
        _enum(enums.TaskStatus, "task_status"), default=enums.TaskStatus.active, index=True
    )
    priority: Mapped[enums.TaskPriority] = mapped_column(
        _enum(enums.TaskPriority, "task_priority"), default=enums.TaskPriority.normal, index=True
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[list[str]] = mapped_column(json_column(), default=list)
    source_capture_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("captures.id"), nullable=True
    )
    source_media_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("media_objects.id"), nullable=True
    )
    snooze_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recurrence: Mapped[dict[str, Any] | None] = mapped_column(json_column(), nullable=True)
    last_nag_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Note(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "notes"

    body: Mapped[str] = mapped_column(Text)
    source_capture_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("captures.id"), nullable=True
    )
    linked_task_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("tasks.id"), nullable=True
    )
    tags: Mapped[list[str]] = mapped_column(json_column(), default=list)


class Reminder(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "reminders"

    task_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tasks.id"), index=True)
    fire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cadence: Mapped[enums.ReminderCadence] = mapped_column(
        _enum(enums.ReminderCadence, "reminder_cadence"), default=enums.ReminderCadence.once
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class CalendarProposal(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "calendar_proposals"

    task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("tasks.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    busy: Mapped[bool] = mapped_column(Boolean, default=True)
    ics_media_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("media_objects.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(json_column(), nullable=True)


class IntegrationAccount(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "integration_accounts"

    provider: Mapped[str] = mapped_column(String(32), index=True)
    scopes: Mapped[list[str]] = mapped_column(json_column(), default=list)
    token_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")


class AuditLog(UUIDPrimaryKey, Base):
    """Append-only audit trail. Summaries are redacted; detail lives in media_objects."""

    __tablename__ = "audit_log"

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor: Mapped[enums.AuditActor] = mapped_column(_enum(enums.AuditActor, "audit_actor"))
    event: Mapped[str] = mapped_column(String(64), index=True)
    capture_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    action_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    detail_ref: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class IdempotencyRecord(UUIDPrimaryKey, Timestamps, Base):
    """Stores prior responses keyed by client Idempotency-Key per endpoint."""

    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("key", "endpoint", name="uq_idempotency_key_endpoint"),)

    key: Mapped[str] = mapped_column(String(128), index=True)
    endpoint: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_json: Mapped[dict[str, Any]] = mapped_column(json_column(), default=dict)
