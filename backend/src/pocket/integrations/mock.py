"""Deterministic mock adapters.

These let the full capture -> interpret -> propose -> approve loop run offline with no
secrets. The LLM mock uses simple keyword routing to emit realistic structured proposals for
the MVP commands, mirroring what a real model would return.
"""

from __future__ import annotations

import hashlib

from pocket.integrations.base import (
    CcJobResult,
    EmailSummary,
    FreeBusySlot,
    GithubIssueRef,
    InterpretRequest,
)
from pocket.schemas.actions import InterpretationResult, ProposedAction


class MockLLM:
    name = "mock"

    def interpret(self, request: InterpretRequest) -> InterpretationResult:
        text = request.transcript.lower().strip()

        if "what's my day" in text or "whats my day" in text or "my day look" in text:
            return InterpretationResult(
                intent="daily_summary",
                model="mock-1",
                actions=[
                    ProposedAction(
                        type="daily_summary",
                        explanation="Assemble today's calendar, tasks, and overdue items.",
                        payload={"include_email": False},
                    )
                ],
            )

        if "get back to me" in text or "did anyone" in text:
            return InterpretationResult(
                intent="email_followup",
                model="mock-1",
                actions=[
                    ProposedAction(
                        type="email_search",
                        explanation="Search the last day of email for job/task replies.",
                        payload={"query": "follow up", "window_days": 1, "focus": "job"},
                    )
                ],
            )

        if "issue" in text and ("fix" in text or "create" in text):
            repo = "OWNER/day-trader-site"
            return InterpretationResult(
                intent="code_task",
                model="mock-1",
                actions=[
                    ProposedAction(
                        type="create_task",
                        explanation="Track the day-trader DB data-pull problem as a task.",
                        payload={
                            "title": "Day trader site: DB data-pull issue",
                            "priority": "high",
                        },
                    ),
                    ProposedAction(
                        type="create_github_issue",
                        explanation=f"Open an issue in {repo} describing the DB data-pull problem.",
                        payload={
                            "repo": repo,
                            "title": "Data pull from database is failing",
                            "body": "The day trader site fails to pull data from the database.",
                        },
                    ),
                    ProposedAction(
                        type="prepare_cc_job",
                        explanation="Prepare a Claude Code job prompt to investigate and fix.",
                        payload={
                            "repo": repo,
                            "prompt": "Investigate and fix the DB data-pull failure.",
                        },
                    ),
                    ProposedAction(
                        type="invoke_cc_job",
                        explanation="Run Claude Code on a new branch (no merge). Requires PIN.",
                        payload={"repo": repo, "prompt_ref": "prepared"},
                    ),
                ],
            )

        if text.startswith("take a note") or "note:" in text:
            body = request.transcript.split(":", 1)[-1].strip() or request.transcript
            return InterpretationResult(
                intent="note",
                model="mock-1",
                actions=[
                    ProposedAction(
                        type="create_note",
                        explanation="Save this as a note.",
                        payload={"body": body},
                    )
                ],
            )

        # Default: treat as a task.
        return InterpretationResult(
            intent="task",
            model="mock-1",
            actions=[
                ProposedAction(
                    type="create_task",
                    explanation="Create a normal-priority task from this request.",
                    payload={"title": request.transcript.strip()[:200], "priority": "normal"},
                )
            ],
        )


class MockGmail:
    name = "mock"

    def search(self, query: str, window_days: int) -> list[EmailSummary]:
        return [
            EmailSummary(
                thread_id="t_mock_1",
                sender="recruiter@example.com",
                subject="Re: your application",
                gist="Wants to schedule a call this week.",
            )
        ]


class MockCalendar:
    name = "mock"

    def free_busy(self, day_iso: str) -> list[FreeBusySlot]:
        # One busy block midday; rest of 9-5 is free.
        return [FreeBusySlot(start=f"{day_iso}T12:00:00", end=f"{day_iso}T13:00:00")]


class MockGithub:
    name = "mock"

    def create_issue(self, repo: str, title: str, body: str, labels: list[str]) -> GithubIssueRef:
        number = int(hashlib.sha256(f"{repo}:{title}".encode()).hexdigest()[:6], 16) % 9000 + 1
        return GithubIssueRef(
            repo=repo, number=number, url=f"https://example.invalid/{repo}/issues/{number}"
        )


class MockClaudeCode:
    name = "mock"

    def invoke(self, repo: str, prompt: str) -> CcJobResult:
        return CcJobResult(
            job_id="cc_mock_1",
            branch="pocket/fix-db-data-pull",
            pr_url=f"https://example.invalid/{repo}/pull/1",
            summary="Mock: opened a branch with a candidate fix. No merge performed.",
        )


class MockStt:
    name = "mock"

    def transcribe(self, audio_path: str) -> str:
        return "(mock server transcription)"
