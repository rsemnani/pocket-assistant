"""Transcript-corrections export endpoint + interpreter current-time injection."""

from __future__ import annotations

from fastapi.testclient import TestClient

from pocket.core.config import Settings
from pocket.domain.interpret import _current_local_time


def _post_capture(client, auth, transcript, raw=None):
    body = {"transcript": transcript}
    if raw is not None:
        body["transcript_raw"] = raw
    return client.post("/v1/captures", json=body, headers=auth)


def test_corrections_lists_only_edited(client: TestClient, auth: dict):
    _post_capture(client, auth, "buy milk", raw="by milk")  # edited
    _post_capture(client, auth, "call mom")  # unedited
    rows = client.get("/v1/captures/corrections", headers=auth).json()
    assert len(rows) == 1
    assert rows[0]["transcript_raw"] == "by milk"
    assert rows[0]["transcript_edited"] == "buy milk"


def test_corrections_requires_auth(client: TestClient):
    assert client.get("/v1/captures/corrections").status_code == 401


def test_corrections_route_not_shadowed_by_capture_id(client: TestClient, auth: dict):
    # "corrections" must hit the export endpoint, not be treated as a capture id.
    resp = client.get("/v1/captures/corrections", headers=auth)
    assert resp.status_code == 200


def test_current_local_time_utc_and_bad_tz():
    s = Settings(assistant_timezone="UTC")
    assert "UTC" in _current_local_time(s)
    bad = Settings(assistant_timezone="Not/AZone")
    # Falls back to UTC instead of raising.
    assert "UTC" in _current_local_time(bad)


def test_interpret_includes_now_in_request(client: TestClient, auth: dict, monkeypatch):
    # The mock LLM ignores `now`, but verify the interpret service sets it on the request.
    captured = {}

    class _Spy:
        name = "spy"

        def interpret(self, request):
            captured["now"] = request.now
            from pocket.schemas.actions import InterpretationResult

            return InterpretationResult(intent="task", actions=[])

    monkeypatch.setattr("pocket.integrations.registry.get_llm", lambda settings=None: _Spy())

    cap = _post_capture(client, auth, "hello").json()["id"]
    client.post(f"/v1/captures/{cap}/interpret", headers=auth)
    assert captured["now"] is not None
    assert "UTC" in captured["now"] or ":" in captured["now"]
