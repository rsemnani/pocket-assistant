"""Unit tests for the server-side sensitivity policy."""

from __future__ import annotations

from pocket.db.enums import ActionType, Sensitivity
from pocket.domain.policy import sensitivity_for


def test_create_task_is_normal():
    assert sensitivity_for(ActionType.create_task, {}) == Sensitivity.normal


def test_github_issue_requires_approval():
    assert sensitivity_for(ActionType.create_github_issue, {}) == Sensitivity.approval


def test_invoke_cc_job_requires_pin():
    assert sensitivity_for(ActionType.invoke_cc_job, {}) == Sensitivity.pin_required


def test_email_draft_requires_pin():
    assert sensitivity_for(ActionType.email_draft, {}) == Sensitivity.pin_required


def test_narrow_email_search_is_approval_but_broad_requires_pin():
    assert sensitivity_for(ActionType.email_search, {"window_days": 1}) == Sensitivity.approval
    assert sensitivity_for(ActionType.email_search, {"window_days": 30}) == Sensitivity.pin_required
