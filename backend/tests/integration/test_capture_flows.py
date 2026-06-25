"""End-to-end API tests for the MVP capture -> propose -> approve flows (mocked)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _capture_and_interpret(client: TestClient, auth: dict, transcript: str) -> dict:
    resp = client.post("/v1/captures", json={"transcript": transcript}, headers=auth)
    assert resp.status_code == 201, resp.text
    capture_id = resp.json()["id"]
    resp = client.post(f"/v1/captures/{capture_id}/interpret", headers=auth)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_healthz(client: TestClient):
    assert client.get("/v1/healthz").json()["status"] == "ok"


def test_requires_auth(client: TestClient):
    assert client.get("/v1/tasks").status_code == 401


def test_daily_summary_flow(client: TestClient, auth: dict):
    data = _capture_and_interpret(client, auth, "what's my day look like?")
    assert data["intent"] == "daily_summary"
    summary = client.get("/v1/summary/daily", headers=auth)
    assert summary.status_code == 200
    assert "spoken_text" in summary.json()


def test_email_followup_is_approval_tier(client: TestClient, auth: dict):
    data = _capture_and_interpret(client, auth, "did anyone get back to me?")
    assert data["intent"] == "email_followup"
    action = data["actions"][0]
    assert action["type"] == "email_search"
    assert action["sensitivity"] == "approval"

    approve = client.post(f"/v1/proposals/{action['id']}/approve", headers=auth)
    assert approve.status_code == 200, approve.text
    # Approval executes immediately in this design, so the action ends 'executed'.
    assert approve.json()["status"] == "executed"
    assert "results" in approve.json()["external_ref"]


def test_create_task_via_proposal_executes(client: TestClient, auth: dict):
    data = _capture_and_interpret(client, auth, "remind me to call the dentist")
    action = data["actions"][0]
    assert action["type"] == "create_task"
    approve = client.post(f"/v1/proposals/{action['id']}/approve", headers=auth)
    assert approve.status_code == 200
    tasks = client.get("/v1/tasks", headers=auth).json()
    assert any("dentist" in t["title"] for t in tasks)


def test_code_task_invoke_cc_requires_pin(client: TestClient, auth: dict):
    data = _capture_and_interpret(
        client, auth, "the day trader site has an issue pulling data. create an issue and fix it"
    )
    assert data["intent"] == "code_task"
    actions = {a["type"]: a for a in data["actions"]}

    # GitHub issue: approval tier, executes without PIN.
    issue = actions["create_github_issue"]
    assert issue["sensitivity"] == "approval"
    r = client.post(f"/v1/proposals/{issue['id']}/approve", headers=auth)
    assert r.status_code == 200
    assert "issue_url" in r.json()["external_ref"]

    # invoke_cc_job: pin_required. Without a session token -> 403.
    invoke = actions["invoke_cc_job"]
    assert invoke["sensitivity"] == "pin_required"
    blocked = client.post(f"/v1/proposals/{invoke['id']}/approve", headers=auth)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "pin_required"

    # Open a PIN session, then approve succeeds.
    sess = client.post("/v1/devices/session/pin", json={"pin": "1234"}, headers=auth)
    assert sess.status_code == 200, sess.text
    session_token = sess.json()["session_token"]
    ok = client.post(
        f"/v1/proposals/{invoke['id']}/approve",
        headers={**auth, "X-Session-Token": session_token},
    )
    assert ok.status_code == 200, ok.text
    assert "branch" in ok.json()["external_ref"]


def test_wrong_pin_rejected(client: TestClient, auth: dict):
    resp = client.post("/v1/devices/session/pin", json={"pin": "9999"}, headers=auth)
    assert resp.status_code == 403
