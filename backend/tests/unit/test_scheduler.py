"""The scheduler's single-iteration runner calls the reminder scan in a session scope."""

from __future__ import annotations

from contextlib import contextmanager

import pocket.workers.scheduler as scheduler
from pocket.workers.reminders import ScanResult


def test_run_once_invokes_scan_in_session(monkeypatch):
    opened = {"scope": False}
    seen_db = object()

    @contextmanager
    def fake_scope():
        opened["scope"] = True
        yield seen_db

    calls = []

    def fake_run_scan(db, now=None):
        calls.append(db)
        return ScanResult(escalated=["t1"], nags=["t2"])

    monkeypatch.setattr(scheduler, "session_scope", fake_scope)
    monkeypatch.setattr(scheduler, "run_scan", fake_run_scan)

    scheduler.run_once()

    assert opened["scope"] is True
    assert calls == [seen_db]
