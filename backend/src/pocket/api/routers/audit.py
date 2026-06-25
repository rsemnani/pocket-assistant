"""Audit log endpoint (paginated, redacted summaries only)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from pocket.api.deps import DbDep, DeviceDep
from pocket.db.models import AuditLog
from pocket.schemas.api import AuditEntryResponse

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("", response_model=list[AuditEntryResponse])
def list_audit(
    db: DbDep,
    device: DeviceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLog]:
    return db.query(AuditLog).order_by(AuditLog.ts.desc()).offset(offset).limit(limit).all()
