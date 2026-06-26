"""Capture endpoints: create (with transcript), edit transcript, interpret, list proposals.

Audio upload is a multipart endpoint; in Phase 1 the transcript is provided by the on-device
STT and audio bytes are optional. Idempotency-Key prevents duplicate captures on retry.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header

from pocket.api.deps import DbDep, DeviceDep, SettingsDep
from pocket.core.errors import ConflictError, NotFoundError
from pocket.core.idempotency import request_hash
from pocket.db.enums import AuditActor, CaptureStatus
from pocket.db.models import Capture, IdempotencyRecord, Interpretation, ProposedAction
from pocket.domain import audit
from pocket.domain.interpret import interpret_capture
from pocket.integrations import registry
from pocket.schemas.api import (
    CaptureCreateRequest,
    CaptureResponse,
    ProposalListResponse,
    ProposedActionResponse,
    TranscriptUpdateRequest,
)

router = APIRouter(prefix="/v1/captures", tags=["captures"])


@router.post("", response_model=CaptureResponse, status_code=201)
def create_capture(
    body: CaptureCreateRequest,
    db: DbDep,
    device: DeviceDep,
    settings: SettingsDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CaptureResponse:
    if idempotency_key:
        existing = (
            db.query(IdempotencyRecord)
            .filter(
                IdempotencyRecord.key == idempotency_key,
                IdempotencyRecord.endpoint == "create_capture",
            )
            .one_or_none()
        )
        rhash = request_hash(body.model_dump(mode="json"))
        if existing:
            if existing.request_hash != rhash:
                raise ConflictError("Idempotency-Key reused with a different request body")
            return CaptureResponse(**existing.response_json)

    # Preserve the original STT output (transcript_raw) distinctly from the edited/sent text
    # (transcript_edited). If the client didn't send a raw value, it was unedited.
    raw = body.transcript_raw if body.transcript_raw is not None else body.transcript
    edited = raw != body.transcript
    capture = Capture(
        device_id=device.id,
        transcript_raw=raw,
        transcript_edited=body.transcript,
        transcription_source=body.transcription_source,
        status=CaptureStatus.received,
        idempotency_key=idempotency_key,
        captured_at=body.captured_at,
    )
    db.add(capture)
    db.flush()
    summary = (
        f"source={body.transcription_source.value} " f"len={len(body.transcript)} edited={edited}"
    )
    audit.record(
        db,
        actor=AuditActor.device,
        event="CAPTURE_RECEIVED",
        summary=summary,
        capture_id=capture.id,
    )

    response = CaptureResponse(
        id=capture.id, status=capture.status, transcript_edited=capture.transcript_edited
    )
    if idempotency_key:
        db.add(
            IdempotencyRecord(
                key=idempotency_key,
                endpoint="create_capture",
                request_hash=request_hash(body.model_dump(mode="json")),
                response_json=response.model_dump(mode="json"),
            )
        )
        db.flush()
    return response


def _get_capture(db: DbDep, capture_id: uuid.UUID) -> Capture:
    capture = db.get(Capture, capture_id)
    if capture is None:
        raise NotFoundError("capture not found")
    return capture


@router.patch("/{capture_id}/transcript", response_model=CaptureResponse)
def edit_transcript(
    capture_id: uuid.UUID, body: TranscriptUpdateRequest, db: DbDep, device: DeviceDep
) -> CaptureResponse:
    capture = _get_capture(db, capture_id)
    capture.transcript_edited = body.transcript
    db.flush()
    return CaptureResponse(
        id=capture.id, status=capture.status, transcript_edited=capture.transcript_edited
    )


@router.post("/{capture_id}/interpret", response_model=ProposalListResponse)
def interpret(
    capture_id: uuid.UUID, db: DbDep, device: DeviceDep, settings: SettingsDep
) -> ProposalListResponse:
    capture = _get_capture(db, capture_id)
    llm = registry.get_llm(settings)
    interpretation = interpret_capture(db, capture, llm)
    actions = (
        db.query(ProposedAction).filter(ProposedAction.interpretation_id == interpretation.id).all()
    )
    return ProposalListResponse(
        capture_id=capture.id,
        intent=interpretation.intent,
        actions=[ProposedActionResponse.model_validate(a) for a in actions],
    )


@router.get("/{capture_id}/proposals", response_model=ProposalListResponse)
def get_proposals(capture_id: uuid.UUID, db: DbDep, device: DeviceDep) -> ProposalListResponse:
    capture = _get_capture(db, capture_id)
    interpretation = (
        db.query(Interpretation)
        .filter(Interpretation.capture_id == capture.id)
        .order_by(Interpretation.created_at.desc())
        .first()
    )
    if interpretation is None:
        raise NotFoundError("capture has not been interpreted yet")
    actions = (
        db.query(ProposedAction).filter(ProposedAction.interpretation_id == interpretation.id).all()
    )
    return ProposalListResponse(
        capture_id=capture.id,
        intent=interpretation.intent,
        actions=[ProposedActionResponse.model_validate(a) for a in actions],
    )
