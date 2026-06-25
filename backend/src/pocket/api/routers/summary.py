"""Daily summary endpoint (read-only)."""

from __future__ import annotations

from fastapi import APIRouter

from pocket.api.deps import DbDep, DeviceDep, SettingsDep
from pocket.domain.summary import build_daily_summary
from pocket.schemas.api import DailySummaryResponse, TaskResponse

router = APIRouter(prefix="/v1/summary", tags=["summary"])


@router.get("/daily", response_model=DailySummaryResponse)
def daily(db: DbDep, device: DeviceDep, settings: SettingsDep) -> DailySummaryResponse:
    data = build_daily_summary(db, settings)
    return DailySummaryResponse(
        spoken_text=data["spoken_text"],
        events=data["events"],
        tasks=[TaskResponse.model_validate(t) for t in data["tasks"]],
        overdue=[TaskResponse.model_validate(t) for t in data["overdue"]],
        completion_prompts=data["completion_prompts"],
    )
