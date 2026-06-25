"""FastAPI dependencies: request context, device auth, and PIN-session enforcement."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from pocket.core.config import Settings, get_settings
from pocket.core.errors import AuthError, PinRequiredError
from pocket.core.security import verify_token
from pocket.db.base import utcnow
from pocket.db.enums import DeviceStatus
from pocket.db.models import Device
from pocket.db.models import Session as SessionModel
from pocket.db.session import get_db

DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing or malformed Authorization header")
    return authorization.split(" ", 1)[1].strip()


def get_current_device(
    db: DbDep,
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Device:
    token = _bearer(authorization)
    devices = db.query(Device).filter(Device.status == DeviceStatus.active).all()
    for device in devices:
        if verify_token(token, device.token_hash, settings.device_token_pepper):
            device.last_seen_at = utcnow()
            return device
    raise AuthError("invalid device token")


DeviceDep = Annotated[Device, Depends(get_current_device)]


def require_pin_session(
    db: DbDep,
    device: DeviceDep,
    settings: SettingsDep,
    request: Request,
    x_session_token: Annotated[str | None, Header()] = None,
) -> SessionModel:
    """Ensure a valid, unexpired PIN-unlocked session exists for sensitive actions."""
    if not x_session_token:
        raise PinRequiredError("a PIN-unlocked session is required for this action")
    now = utcnow()
    sessions = (
        db.query(SessionModel)
        .filter(SessionModel.device_id == device.id, SessionModel.expires_at > now)
        .all()
    )
    for session in sessions:
        if verify_token(x_session_token, session.token_hash, settings.device_token_pepper):
            return session
    raise PinRequiredError("session token invalid or expired; re-enter PIN")


def request_id(request: Request) -> uuid.UUID:
    rid = getattr(request.state, "request_id", None)
    return rid if isinstance(rid, uuid.UUID) else uuid.uuid4()
