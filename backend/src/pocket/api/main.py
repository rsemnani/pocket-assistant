"""FastAPI application factory."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request

from pocket.api.routers import audit, captures, devices, proposals, summary, tasks
from pocket.core.config import get_settings
from pocket.core.errors import register_error_handlers
from pocket.core.logging import configure_logging, get_logger

log = get_logger("pocket.api")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Pocket Assistant API",
        version="0.1.0",
        description="Voice-capture personal assistant backend (Phase 1, mocked integrations).",
    )

    register_error_handlers(app)

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = uuid.uuid4()
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(request.state.request_id)
        return response

    @app.get("/v1/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(devices.router)
    app.include_router(captures.router)
    app.include_router(proposals.router)
    app.include_router(tasks.router)
    app.include_router(summary.router)
    app.include_router(audit.router)

    return app


app = create_app()
