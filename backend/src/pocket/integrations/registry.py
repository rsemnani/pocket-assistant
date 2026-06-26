"""Provider registry: selects adapters from settings.

Phase 1 ships mock adapters only. Real adapters are registered here in later phases without
changing call sites — domain code depends on the Protocols in `base`, not concrete classes.
"""

from __future__ import annotations

from pocket.core.config import Settings, get_settings
from pocket.integrations import base, mock


def get_llm(settings: Settings | None = None) -> base.LLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider == "mock":
        return mock.MockLLM()
    if settings.llm_provider == "claude_cli":
        from pocket.integrations.claude_cli import ClaudeCliLLM  # subscription via local CLI

        return ClaudeCliLLM(settings)
    if settings.llm_provider == "claude":
        from pocket.integrations.claude import ClaudeLLM  # lazy: optional anthropic dep

        return ClaudeLLM(settings)
    raise NotImplementedError(f"LLM provider '{settings.llm_provider}' not implemented yet")


def get_gmail(settings: Settings | None = None) -> base.GmailProvider:
    settings = settings or get_settings()
    if settings.gmail_provider == "mock":
        return mock.MockGmail()
    raise NotImplementedError(f"Gmail provider '{settings.gmail_provider}' not implemented yet")


def get_calendar(settings: Settings | None = None) -> base.CalendarProvider:
    settings = settings or get_settings()
    if settings.calendar_provider == "mock":
        return mock.MockCalendar()
    raise NotImplementedError(
        f"Calendar provider '{settings.calendar_provider}' not implemented yet"
    )


def get_github(settings: Settings | None = None) -> base.GithubProvider:
    settings = settings or get_settings()
    if settings.github_provider == "mock":
        return mock.MockGithub()
    raise NotImplementedError(f"GitHub provider '{settings.github_provider}' not implemented yet")


def get_claude_code(settings: Settings | None = None) -> base.ClaudeCodeProvider:
    settings = settings or get_settings()
    if settings.claude_code_provider == "mock":
        return mock.MockClaudeCode()
    raise NotImplementedError("Claude Code provider 'real' not implemented yet")
