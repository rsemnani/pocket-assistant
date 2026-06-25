"""Interpretation service: run the LLM, validate output, persist proposals.

Context discipline: task context is included by default; email/calendar context is only
fetched when the command clearly requires it (decided before the model is called).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from pocket.db.enums import AuditActor, CaptureStatus
from pocket.db.models import Capture, Interpretation, ProposedAction, Task
from pocket.domain import audit
from pocket.domain.policy import sensitivity_for
from pocket.integrations.base import InterpretRequest, LLMProvider


def _needs_email(transcript: str) -> bool:
    t = transcript.lower()
    return any(k in t for k in ("email", "get back to me", "did anyone", "inbox", "reply"))


def _needs_calendar(transcript: str) -> bool:
    t = transcript.lower()
    return any(k in t for k in ("calendar", "carve out", "schedule", "my day", "free time"))


def interpret_capture(db: Session, capture: Capture, llm: LLMProvider) -> Interpretation:
    """Interpret a capture into validated, persisted proposed actions."""
    transcript = capture.transcript_edited or capture.transcript_raw or ""

    task_context = [
        {"id": str(t.id), "title": t.title, "status": t.status.value, "priority": t.priority.value}
        for t in db.query(Task).limit(50).all()
    ]

    request = InterpretRequest(
        transcript=transcript,
        task_context=task_context,
        allow_email=_needs_email(transcript),
        allow_calendar=_needs_calendar(transcript),
    )

    capture.status = CaptureStatus.interpreting
    result = llm.interpret(request)  # already a validated Pydantic InterpretationResult

    interpretation = Interpretation(
        capture_id=capture.id,
        provider=llm.name,
        model=result.model,
        intent=result.intent,
        validation_status="valid",
    )
    db.add(interpretation)
    db.flush()

    for action in result.actions:
        sensitivity = sensitivity_for(action.type, action.payload)
        db.add(
            ProposedAction(
                interpretation_id=interpretation.id,
                type=action.type,
                payload=action.payload,
                explanation=action.explanation,
                sensitivity=sensitivity,
            )
        )

    capture.status = CaptureStatus.proposed
    db.flush()

    audit.record(
        db,
        actor=AuditActor.llm,
        event="INTERPRETATION_CREATED",
        summary=f"intent={result.intent} provider={llm.name} actions={len(result.actions)}",
        capture_id=capture.id,
    )
    return interpretation
