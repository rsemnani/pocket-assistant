"""Raw STT transcript is stored distinctly from the edited/sent text (training data)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from pocket.db.models import Capture


def test_raw_and_edited_stored_distinctly(client: TestClient, auth: dict, session_factory):
    resp = client.post(
        "/v1/captures",
        json={"transcript": "buy milk", "transcript_raw": "by milk"},
        headers=auth,
    )
    assert resp.status_code == 201
    capture_id = uuid.UUID(resp.json()["id"])

    db = session_factory()
    cap = db.get(Capture, capture_id)
    assert cap.transcript_raw == "by milk"
    assert cap.transcript_edited == "buy milk"
    db.close()


def test_raw_defaults_to_transcript_when_omitted(client: TestClient, auth: dict, session_factory):
    resp = client.post("/v1/captures", json={"transcript": "hello world"}, headers=auth)
    capture_id = uuid.UUID(resp.json()["id"])

    db = session_factory()
    cap = db.get(Capture, capture_id)
    assert cap.transcript_raw == "hello world"
    assert cap.transcript_edited == "hello world"
    db.close()


def test_audit_records_edited_flag(client: TestClient, auth: dict):
    client.post(
        "/v1/captures",
        json={"transcript": "buy milk", "transcript_raw": "by milk"},
        headers=auth,
    )
    entries = client.get("/v1/audit", headers=auth).json()
    received = [e for e in entries if e["event"] == "CAPTURE_RECEIVED"]
    assert received
    assert any("edited=True" in e["summary"] for e in received)
