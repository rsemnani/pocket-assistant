"""Input-validation hardening at the API boundary."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_invalid_transcription_source_rejected_422(client: TestClient, auth: dict):
    resp = client.post(
        "/v1/captures",
        json={"transcript": "hi", "transcription_source": "'; DROP TABLE captures; --"},
        headers=auth,
    )
    # Bad enum value is rejected cleanly (422), not a 500 / not executed.
    assert resp.status_code == 422


def test_non_uuid_path_param_rejected_422(client: TestClient, auth: dict):
    resp = client.post("/v1/captures/not-a-uuid/interpret", headers=auth)
    assert resp.status_code == 422


def test_empty_transcript_rejected(client: TestClient, auth: dict):
    resp = client.post("/v1/captures", json={"transcript": ""}, headers=auth)
    assert resp.status_code == 422
