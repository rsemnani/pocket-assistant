"""Server-side sensitivity policy for actions.

Sensitivity is assigned by the backend, never trusted from the LLM. This is the single
source of truth for what requires plain approval vs a PIN-unlocked session.
"""

from __future__ import annotations

from typing import Any

from pocket.db.enums import ActionType, Sensitivity

_PIN_REQUIRED: frozenset[ActionType] = frozenset(
    {
        ActionType.invoke_cc_job,
        ActionType.email_draft,
    }
)

_NORMAL: frozenset[ActionType] = frozenset(
    {
        ActionType.create_task,
        ActionType.update_task,
        ActionType.create_note,
        ActionType.daily_summary,
        ActionType.clarify,
    }
)


def sensitivity_for(action_type: ActionType, payload: dict[str, Any]) -> Sensitivity:
    """Return the required sensitivity tier for an action.

    Broad email searches (large window) escalate to pin_required even though a narrow search
    is only `approval`.
    """
    if action_type in _PIN_REQUIRED:
        return Sensitivity.pin_required

    if action_type == ActionType.email_search:
        window = int(payload.get("window_days", 1) or 1)
        return Sensitivity.pin_required if window > 7 else Sensitivity.approval

    if action_type in _NORMAL:
        return Sensitivity.normal

    # create_github_issue, propose_event, prepare_cc_job, email_search(narrow) -> approval
    return Sensitivity.approval
