"""Shared pytest fixtures: in-memory SQLite DB + a TestClient with overridden settings.

No external services, no secrets, no Postgres required.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# Ensure deterministic, offline config BEFORE app imports read settings.
os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("DEVICE_TOKEN_PEPPER", "test-pepper")
os.environ.setdefault("DEV_SESSION_PIN", "1234")
os.environ.setdefault("GITHUB_REPO_ALLOWLIST", "OWNER/day-trader-site")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import StaticPool, create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

import pocket.db.session as db_session  # noqa: E402
from pocket.api.main import create_app  # noqa: E402
from pocket.db.base import Base  # noqa: E402


@pytest.fixture()
def engine():  # type: ignore[no-untyped-def]
    # Single shared in-memory DB across connections within the test.
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session_factory(engine):  # type: ignore[no-untyped-def]
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture()
def db(session_factory) -> Iterator[Session]:  # type: ignore[no-untyped-def]
    session = session_factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture()
def client(engine, session_factory, monkeypatch) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    # Point the app's session machinery at the test engine/factory.
    monkeypatch.setattr(db_session, "_engine", engine, raising=False)
    monkeypatch.setattr(db_session, "_SessionFactory", session_factory, raising=False)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def device_token(client: TestClient) -> str:
    resp = client.post(
        "/v1/devices/register", json={"registration_code": "pair-code", "name": "test-robin"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["device_token"]


@pytest.fixture()
def auth(device_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {device_token}"}
