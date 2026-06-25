"""Integration interfaces (Protocols) shared by mock and real adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from pocket.schemas.actions import InterpretationResult


@dataclass(frozen=True)
class InterpretRequest:
    transcript: str
    intent_hint: str | None = None
    task_context: list[dict[str, Any]] = field(default_factory=list)
    allow_email: bool = False
    allow_calendar: bool = False


class LLMProvider(Protocol):
    name: str

    def interpret(self, request: InterpretRequest) -> InterpretationResult: ...


@dataclass(frozen=True)
class EmailSummary:
    thread_id: str
    sender: str
    subject: str
    gist: str


class GmailProvider(Protocol):
    name: str

    def search(self, query: str, window_days: int) -> list[EmailSummary]: ...


@dataclass(frozen=True)
class FreeBusySlot:
    start: str  # ISO 8601
    end: str


class CalendarProvider(Protocol):
    name: str

    def free_busy(self, day_iso: str) -> list[FreeBusySlot]: ...


@dataclass(frozen=True)
class GithubIssueRef:
    repo: str
    number: int
    url: str


class GithubProvider(Protocol):
    name: str

    def create_issue(
        self, repo: str, title: str, body: str, labels: list[str]
    ) -> GithubIssueRef: ...


@dataclass(frozen=True)
class CcJobResult:
    job_id: str
    branch: str
    pr_url: str | None
    summary: str


class ClaudeCodeProvider(Protocol):
    name: str

    def invoke(self, repo: str, prompt: str) -> CcJobResult: ...


class SttProvider(Protocol):
    name: str

    def transcribe(self, audio_path: str) -> str: ...
