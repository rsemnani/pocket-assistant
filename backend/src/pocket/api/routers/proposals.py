"""Approve / reject proposed actions.

`pin_required` actions are gated by `require_pin_session` (a valid X-Session-Token from a
prior PIN unlock). Execution is idempotent on the action's terminal state.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from pocket.api.deps import DbDep, DeviceDep, SettingsDep, require_pin_session
from pocket.core.errors import ConflictError, NotFoundError, PinRequiredError
from pocket.db.enums import ActionStatus, AuditActor, Sensitivity
from pocket.db.models import ProposedAction
from pocket.db.models import Session as SessionModel
from pocket.domain import audit
from pocket.domain.execute import ExecutionError, execute_action
from pocket.schemas.api import ApproveResponse

router = APIRouter(prefix="/v1/proposals", tags=["proposals"])


def _get_action(db: DbDep, action_id: uuid.UUID) -> ProposedAction:
    action = db.get(ProposedAction, action_id)
    if action is None:
        raise NotFoundError("proposed action not found")
    return action


def _maybe_session(
    db: DbDep,
    device: DeviceDep,
    settings: SettingsDep,
    request: Request,
    x_session_token: Annotated[str | None, Header()] = None,
) -> SessionModel | None:
    """Validate a session token if present; return None if absent (checked per-action)."""
    if not x_session_token:
        return None
    return require_pin_session(db, device, settings, request, x_session_token)


@router.post("/{action_id}/approve", response_model=ApproveResponse)
def approve(
    action_id: uuid.UUID,
    db: DbDep,
    device: DeviceDep,
    settings: SettingsDep,
    session: Annotated[SessionModel | None, Depends(_maybe_session)] = None,
) -> ApproveResponse:
    action = _get_action(db, action_id)

    # Idempotent replay: already executed -> return prior result.
    if action.status == ActionStatus.executed:
        return ApproveResponse(
            action_id=action.id, status=action.status, external_ref=action.external_ref
        )
    if action.status in (ActionStatus.rejected, ActionStatus.executing):
        raise ConflictError(f"action is '{action.status.value}' and cannot be approved")

    if action.sensitivity == Sensitivity.pin_required and session is None:
        raise PinRequiredError("this action requires a PIN-unlocked session (X-Session-Token)")

    action.status = ActionStatus.approved
    audit.record(
        db,
        actor=AuditActor.user,
        event="ACTION_APPROVED",
        summary=f"type={action.type.value} sensitivity={action.sensitivity.value}",
        action_id=action.id,
    )

    try:
        ref = execute_action(db, action, settings)
    except ExecutionError as exc:
        raise ConflictError(f"execution failed: {exc}") from exc

    return ApproveResponse(action_id=action.id, status=action.status, external_ref=ref)


@router.post("/{action_id}/reject", response_model=ApproveResponse)
def reject(action_id: uuid.UUID, db: DbDep, device: DeviceDep) -> ApproveResponse:
    action = _get_action(db, action_id)
    if action.status == ActionStatus.executed:
        raise ConflictError("action already executed; cannot reject")
    action.status = ActionStatus.rejected
    audit.record(
        db,
        actor=AuditActor.user,
        event="ACTION_REJECTED",
        summary=f"type={action.type.value}",
        action_id=action.id,
    )
    return ApproveResponse(action_id=action.id, status=action.status)
