"""Unit tests for the subscription Claude CLI provider using an injected fake runner."""

from __future__ import annotations

import json

import pytest

from pocket.core.config import Settings
from pocket.db.enums import ActionType
from pocket.integrations.base import InterpretRequest
from pocket.integrations.claude import LLMValidationError
from pocket.integrations.claude_cli import ClaudeCliLLM, _extract_json_object


def _settings() -> Settings:
    return Settings(llm_provider="claude_cli", claude_cli_path="claude")


def _runner_returning(*replies: str):
    calls: list[str] = []

    def run(prompt: str) -> str:
        calls.append(prompt)
        return replies[len(calls) - 1]

    run.calls = calls  # type: ignore[attr-defined]
    return run


def test_parses_plain_json_reply():
    reply = json.dumps(
        {
            "intent": "task",
            "actions": [
                {"type": "create_task", "explanation": "Buy milk", "payload": {"title": "Buy milk"}}
            ],
        }
    )
    runner = _runner_returning(reply)
    llm = ClaudeCliLLM(_settings(), runner=runner)

    result = llm.interpret(InterpretRequest(transcript="remind me to buy milk"))

    assert result.intent == "task"
    assert result.actions[0].type == ActionType.create_task
    # The transcript and context flags reached the prompt.
    assert "Transcript: remind me to buy milk" in runner.calls[0]
    assert "Email context permitted: False" in runner.calls[0]


def test_extracts_json_from_fenced_or_prose_reply():
    reply = 'Sure! Here you go:\n```json\n{"intent":"note","actions":[]}\n```\nLet me know.'
    llm = ClaudeCliLLM(_settings(), runner=_runner_returning(reply))
    result = llm.interpret(InterpretRequest(transcript="take a note"))
    assert result.intent == "note"
    assert result.actions == []


def test_repairs_then_succeeds():
    bad = "not json at all"
    good = json.dumps(
        {
            "intent": "task",
            "actions": [{"type": "create_task", "explanation": "x", "payload": {"title": "t"}}],
        }
    )
    runner = _runner_returning(bad, good)
    llm = ClaudeCliLLM(_settings(), runner=runner)

    result = llm.interpret(InterpretRequest(transcript="hi"))

    assert result.actions[0].type == ActionType.create_task
    assert len(runner.calls) == 2  # one repair round-trip
    assert "was not valid" in runner.calls[1]


def test_raises_after_failed_repair():
    runner = _runner_returning("garbage", "still garbage")
    llm = ClaudeCliLLM(_settings(), runner=runner)
    with pytest.raises(LLMValidationError):
        llm.interpret(InterpretRequest(transcript="hi"))


def test_extract_json_object_helper():
    assert _extract_json_object('prefix {"a": 1} suffix') == {"a": 1}
    assert _extract_json_object('{"nested": {"b": 2}}') == {"nested": {"b": 2}}
    with pytest.raises(ValueError):
        _extract_json_object("no object here")
