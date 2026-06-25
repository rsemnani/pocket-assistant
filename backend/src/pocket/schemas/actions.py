"""Canonical structured-action contract.

The LLM is constrained to emit a list of ProposedAction objects matching this schema. The
backend validates every LLM response against it before persisting. The LLM never executes
anything — it only proposes. Sensitivity is assigned server-side (see domain.policy), not
trusted from the model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from pocket.db.enums import ActionType, Sensitivity, TaskPriority


class CreateTaskPayload(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    notes: str | None = None
    priority: TaskPriority = TaskPriority.normal
    due_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)


class UpdateTaskPayload(BaseModel):
    task_id: str
    title: str | None = None
    notes: str | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None


class CreateNotePayload(BaseModel):
    body: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    linked_task_title: str | None = None


class ProposeEventPayload(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    start_at: datetime
    end_at: datetime
    busy: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)


class EmailSearchPayload(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    window_days: int = Field(default=1, ge=1, le=30)
    focus: Literal["job", "task", "general"] = "general"


class EmailDraftPayload(BaseModel):
    to: str
    subject: str
    body: str


class CreateGithubIssuePayload(BaseModel):
    repo: str = Field(description="OWNER/name; must be on the configured allowlist")
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(default="")
    labels: list[str] = Field(default_factory=list)


class PrepareCcJobPayload(BaseModel):
    repo: str
    prompt: str = Field(min_length=1)
    linked_issue: str | None = None


class InvokeCcJobPayload(BaseModel):
    repo: str
    prompt_ref: str = Field(description="ID of a previously prepared CC job")


class ClarifyPayload(BaseModel):
    question: str
    options: list[str] = Field(default_factory=list)


class DailySummaryPayload(BaseModel):
    include_email: bool = False


# Discriminated union keeps payload typing strict per action type.
ActionPayload = Annotated[
    CreateTaskPayload
    | UpdateTaskPayload
    | CreateNotePayload
    | ProposeEventPayload
    | EmailSearchPayload
    | EmailDraftPayload
    | CreateGithubIssuePayload
    | PrepareCcJobPayload
    | InvokeCcJobPayload
    | ClarifyPayload
    | DailySummaryPayload,
    Field(union_mode="left_to_right"),
]


class ProposedAction(BaseModel):
    type: ActionType
    explanation: str = Field(min_length=1, description="Plain-language 'what I will do'.")
    payload: dict[str, Any] = Field(default_factory=dict)
    # Sensitivity is advisory from the LLM; the backend overrides with its own policy.
    sensitivity: Sensitivity | None = None


class InterpretationResult(BaseModel):
    """The validated structured output of an LLM interpretation."""

    intent: str
    actions: list[ProposedAction] = Field(default_factory=list)
    model: str | None = None
