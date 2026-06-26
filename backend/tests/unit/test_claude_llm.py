"""Unit tests for the Claude LLM adapter using a fake Anthropic client (no real calls)."""

from __future__ import annotations

import pytest

from pocket.core.config import Settings
from pocket.db.enums import ActionType
from pocket.integrations.base import InterpretRequest
from pocket.integrations.claude import ClaudeLLM, LLMValidationError


class _FakeBlock:
    def __init__(self, data: dict) -> None:
        self.type = "tool_use"
        self.input = data


class _FakeResponse:
    def __init__(self, data: dict) -> None:
        self.content = [_FakeBlock(data)]


class _FakeMessages:
    def __init__(self, outputs: list[dict]) -> None:
        self._outputs = list(outputs)
        self.calls: list[dict] = []

    def create(self, **kwargs: object) -> _FakeResponse:
        self.calls.append(kwargs)
        return _FakeResponse(self._outputs.pop(0))


class _FakeClient:
    def __init__(self, outputs: list[dict]) -> None:
        self.messages = _FakeMessages(outputs)


def _settings() -> Settings:
    return Settings(llm_provider="claude", llm_model="claude-opus-4-8", llm_api_key="unused")


def test_parses_forced_tool_output():
    out = {
        "intent": "task",
        "actions": [
            {
                "type": "create_task",
                "explanation": "Create a task to buy milk.",
                "payload": {"title": "Buy milk", "priority": "normal"},
            }
        ],
    }
    client = _FakeClient([out])
    llm = ClaudeLLM(_settings(), client=client)

    result = llm.interpret(InterpretRequest(transcript="remind me to buy milk"))

    assert result.intent == "task"
    assert result.actions[0].type == ActionType.create_task
    assert result.model == "claude-opus-4-8"
    # Forced tool use was requested.
    call = client.messages.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "emit_actions"}
    assert call["model"] == "claude-opus-4-8"


def test_context_flags_passed_into_prompt():
    out = {
        "intent": "note",
        "actions": [{"type": "create_note", "explanation": "x", "payload": {"body": "hi"}}],
    }
    client = _FakeClient([out])
    llm = ClaudeLLM(_settings(), client=client)

    llm.interpret(
        InterpretRequest(transcript="take a note", allow_email=False, allow_calendar=True)
    )

    user_msg = client.messages.calls[0]["messages"][0]["content"]
    assert "Email context permitted: False" in user_msg
    assert "Calendar context permitted: True" in user_msg


def test_repairs_invalid_then_succeeds():
    bad = {"intent": "task", "actions": [{"type": "NOT_A_TYPE", "explanation": "x", "payload": {}}]}
    good = {
        "intent": "task",
        "actions": [{"type": "create_task", "explanation": "x", "payload": {"title": "t"}}],
    }
    client = _FakeClient([bad, good])
    llm = ClaudeLLM(_settings(), client=client)

    result = llm.interpret(InterpretRequest(transcript="hi"))

    assert result.actions[0].type == ActionType.create_task
    assert len(client.messages.calls) == 2  # one repair round-trip


def test_raises_after_failed_repair():
    bad = {"intent": "x", "actions": [{"type": "NOPE", "explanation": "x", "payload": {}}]}
    client = _FakeClient([bad, bad])
    llm = ClaudeLLM(_settings(), client=client)

    with pytest.raises(LLMValidationError):
        llm.interpret(InterpretRequest(transcript="hi"))


def test_missing_tool_call_raises():
    class _EmptyResp:
        content: list = []

    class _EmptyClient:
        class messages:  # noqa: N801
            @staticmethod
            def create(**_: object) -> _EmptyResp:
                return _EmptyResp()

    llm = ClaudeLLM(_settings(), client=_EmptyClient())
    with pytest.raises(LLMValidationError):
        llm.interpret(InterpretRequest(transcript="hi"))
