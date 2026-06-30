"""Reminder/escalation scheduler.

A long-running worker that periodically runs the reminder scan (escalate overdue tasks to
high priority, mark which tasks are due for a nag). Runs as its own container/process so it's
independent of the API. Run with: `python -m pocket.workers.scheduler`.
"""

from __future__ import annotations

import time

from pocket.core.config import get_settings
from pocket.core.logging import configure_logging, get_logger
from pocket.db.session import session_scope
from pocket.workers.reminders import run_scan

log = get_logger("pocket.scheduler")


def run_once() -> None:
    """Run a single reminder scan inside a transactional session."""
    with session_scope() as db:
        result = run_scan(db)
    log.info("reminder_scan", escalated=len(result.escalated), nags=len(result.nags))


def main() -> None:  # pragma: no cover - process entry point
    settings = get_settings()
    configure_logging(settings.log_level)
    interval = settings.scan_interval_seconds
    log.info("scheduler_start", interval_seconds=interval)
    while True:
        try:
            run_once()
        except Exception as exc:  # noqa: BLE001 - keep the loop alive on transient errors
            log.error("scan_failed", error=type(exc).__name__)
        time.sleep(interval)


if __name__ == "__main__":  # pragma: no cover
    main()
