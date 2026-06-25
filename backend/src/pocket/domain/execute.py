"""Execute an approved ProposedAction via the appropriate integration adapter.

Idempotent where it creates resources. Returns an external_ref dict persisted on the action.
PIN gating is enforced by the API layer before this is called; this module assumes the
session requirement has already been satisfied.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from pocket.core.config import Settings, get_settings
from pocket.db.enums import ActionStatus, ActionType, AuditActor, TaskPriority
from pocket.db.models import Note, ProposedAction, Task
from pocket.domain import audit
from pocket.integrations import registry


class ExecutionError(Exception):
    pass


def execute_action(
    db: Session, action: ProposedAction, settings: Settings | None = None
) -> dict[str, Any]:
    """Run an approved action and return its external reference."""
    settings = settings or get_settings()
    payload = action.payload or {}
    action.status = ActionStatus.executing
    db.flush()

    try:
        ref = _dispatch(db, action.type, payload, settings)
    except Exception as exc:  # noqa: BLE001 - record then re-raise as ExecutionError
        action.status = ActionStatus.failed
        audit.record(
            db,
            actor=AuditActor.worker,
            event="ACTION_FAILED",
            summary=f"type={action.type.value} error={type(exc).__name__}",
            action_id=action.id,
        )
        raise ExecutionError(str(exc)) from exc

    action.status = ActionStatus.executed
    action.external_ref = ref
    audit.record(
        db,
        actor=AuditActor.worker,
        event="ACTION_EXECUTED",
        summary=f"type={action.type.value} ref={list(ref.keys())}",
        action_id=action.id,
    )
    return ref


def _dispatch(
    db: Session, action_type: ActionType, payload: dict[str, Any], settings: Settings
) -> dict[str, Any]:
    if action_type == ActionType.create_task:
        task = Task(
            title=payload["title"],
            notes=payload.get("notes"),
            priority=TaskPriority(payload.get("priority", "normal")),
            tags=payload.get("tags", []),
        )
        db.add(task)
        db.flush()
        return {"task_id": str(task.id)}

    if action_type == ActionType.create_note:
        note = Note(body=payload["body"], tags=payload.get("tags", []))
        db.add(note)
        db.flush()
        return {"note_id": str(note.id)}

    if action_type == ActionType.create_github_issue:
        repo = payload["repo"]
        if settings.github_repo_allowlist_set and repo not in settings.github_repo_allowlist_set:
            raise ExecutionError(f"repo '{repo}' is not on the allowlist")
        gh = registry.get_github(settings)
        issue = gh.create_issue(
            repo, payload["title"], payload.get("body", ""), payload.get("labels", [])
        )
        return {"issue_url": issue.url, "issue_number": issue.number, "repo": issue.repo}

    if action_type == ActionType.email_search:
        gmail = registry.get_gmail(settings)
        results = gmail.search(payload["query"], int(payload.get("window_days", 1)))
        return {
            "results": [{"sender": r.sender, "subject": r.subject, "gist": r.gist} for r in results]
        }

    if action_type == ActionType.prepare_cc_job:
        # Preparation only persists the prompt reference; no code runs here.
        return {"prepared": True, "repo": payload["repo"]}

    if action_type == ActionType.invoke_cc_job:
        repo = payload["repo"]
        if settings.github_repo_allowlist_set and repo not in settings.github_repo_allowlist_set:
            raise ExecutionError(f"repo '{repo}' is not on the allowlist")
        cc = registry.get_claude_code(settings)
        result = cc.invoke(repo, payload.get("prompt", ""))
        return {"job_id": result.job_id, "branch": result.branch, "pr_url": result.pr_url}

    if action_type == ActionType.daily_summary:
        return {"deferred": "computed by /v1/summary/daily"}

    raise ExecutionError(f"no executor for action type '{action_type.value}'")
