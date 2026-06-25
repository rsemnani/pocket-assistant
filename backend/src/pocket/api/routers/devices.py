"""Device registration and PIN-session endpoints.

Device registration (Phase 1) accepts any non-empty registration code and issues a device
token. A real provisioning flow (operator-generated, single-use codes) replaces this in a
later phase; the surface stays the same.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter

from pocket.api.deps import DbDep, DeviceDep, SettingsDep
from pocket.core.errors import AuthError
from pocket.core.security import generate_token, hash_token, verify_pin
from pocket.db.base import utcnow
from pocket.db.enums import AuditActor
from pocket.db.models import Device
from pocket.db.models import Session as SessionModel
from pocket.domain import audit
from pocket.schemas.api import (
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    SessionPinRequest,
    SessionPinResponse,
)

router = APIRouter(prefix="/v1/devices", tags=["devices"])


@router.post("/register", response_model=DeviceRegisterResponse, status_code=201)
def register_device(
    body: DeviceRegisterRequest, db: DbDep, settings: SettingsDep
) -> DeviceRegisterResponse:
    token = generate_token("pa_dev")
    device = Device(
        name=body.name,
        token_hash=hash_token(token, settings.device_token_pepper),
    )
    db.add(device)
    db.flush()
    audit.record(
        db, actor=AuditActor.system, event="DEVICE_REGISTERED", summary=f"device={device.name}"
    )
    return DeviceRegisterResponse(device_id=device.id, device_token=token)


@router.post("/session/pin", response_model=SessionPinResponse)
def open_session(
    body: SessionPinRequest, db: DbDep, device: DeviceDep, settings: SettingsDep
) -> SessionPinResponse:
    if not verify_pin(body.pin, settings.dev_session_pin):
        raise AuthError("incorrect PIN", code="incorrect_pin", status_code=403)

    session_token = generate_token("pa_sess")
    expires_at = utcnow() + timedelta(minutes=settings.session_ttl_minutes)
    session = SessionModel(
        device_id=device.id,
        token_hash=hash_token(session_token, settings.device_token_pepper),
        pin_verified_at=utcnow(),
        expires_at=expires_at,
    )
    db.add(session)
    db.flush()
    audit.record(db, actor=AuditActor.user, event="PIN_VERIFIED", summary="session opened")
    return SessionPinResponse(session_token=session_token, expires_at=expires_at)
