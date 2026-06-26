"""Real Claude (Anthropic) LLM provider.

Implements the LLMProvider interface using the Anthropic Messages API with **forced
tool use** to obtain structured action proposals. The model never executes anything — it
only emits proposals matching the canonical action schema, which the backend then validates
(Pydantic) and gates behind approval/PIN per the server-side sensitivity policy.

Defaults to `claude-opus-4-8` (configurable via LLM_MODEL). The `anthropic` package is an
optional dependency, imported lazily so the app/tests run fully mocked without it.

Design references: DESIGN.md §9 (LLM/tool-calling). Activating this provider requires a real
API key in the deployment env and explicit approval — until then LLM_PROVIDER stays `mock`.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from pocket.core.config import Settings, get_settings
from pocket.db.enums import ActionType
from pocket.integrations.base import InterpretRequest
from pocket.schemas.actions import InterpretationResult

DEFAULT_MODEL = "claude-opus-4-8"
MAX_REPAIRS = 1

_SYSTEM_PROMPT = """You are the interpretation engine for Pocket Assistant, a voice-capture
personal assistant. You receive a short, already-transcribed spoken command plus optional
context, and you must decide the user's intent and propose structured actions by calling the
`emit_actions` tool.

Hard rules:
- You ONLY propose actions. You never execute anything and never claim to have done anything.
- Call `emit_actions` exactly once. Do not write prose outside the tool call.
- Use the provided task context; do not invent tasks, emails, or events that aren't given.
- Only reference email or calendar when the command clearly requires it (the request says
  whether email/calendar context is permitted). If it isn't permitted, do not propose
  email/calendar actions.
- Prefer the least invasive action. If a coding/repo target is ambiguous or there are
  multiple options, propose a single `clarify` action listing the options instead of guessing.
- Keep each `explanation` short and in plain language: what you will do, from the user's view.
- Put action-specific parameters in `payload` (e.g. a task's title/priority, an issue's
  repo/title/body). Keep payload minimal and well-formed.
"""


class LLMValidationError(Exception):
    """Raised when the model's structured output cannot be validated after repair."""


def _action_tool() -> dict[str, Any]:
    return {
        "name": "emit_actions",
        "description": "Emit the interpreted intent and the list of proposed actions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": (
                        "Short intent label, e.g. daily_summary, email_followup, "
                        "code_task, note, task."
                    ),
                },
                "actions": {
                    "type": "array",
                    "description": "Ordered list of proposed actions.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [t.value for t in ActionType],
                            },
                            "explanation": {
                                "type": "string",
                                "description": "Plain-language 'what I will do'.",
                            },
                            "payload": {
                                "type": "object",
                                "description": "Action-specific parameters.",
                            },
                        },
                        "required": ["type", "explanation", "payload"],
                    },
                },
            },
            "required": ["intent", "actions"],
        },
    }


class ClaudeLLM:
    name = "claude"

    def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = self._settings.llm_model or DEFAULT_MODEL
        if client is None:
            import anthropic  # lazy: optional dependency

            client = anthropic.Anthropic(api_key=self._settings.llm_api_key)
        self._client: Any = client

    def interpret(self, request: InterpretRequest) -> InterpretationResult:
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": self._build_user_content(request)}
        ]
        last_error: str | None = None

        for attempt in range(MAX_REPAIRS + 1):
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                tools=[_action_tool()],
                tool_choice={"type": "tool", "name": "emit_actions"},
                messages=messages,
            )
            payload = self._extract_tool_input(response)
            try:
                return InterpretationResult.model_validate({**payload, "model": self._model})
            except ValidationError as exc:
                last_error = str(exc)
                if attempt >= MAX_REPAIRS:
                    break
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "The previous emit_actions call failed validation:\n"
                            f"{last_error}\n"
                            "Call emit_actions again with corrected, schema-valid actions."
                        ),
                    }
                )

        raise LLMValidationError(last_error or "invalid LLM output")

    def _build_user_content(self, request: InterpretRequest) -> str:
        parts = [f"Transcript: {request.transcript.strip()}"]
        parts.append(f"Email context permitted: {request.allow_email}")
        parts.append(f"Calendar context permitted: {request.allow_calendar}")
        if request.task_context:
            parts.append("Existing tasks (JSON):")
            parts.append(json.dumps(request.task_context, separators=(",", ":")))
        else:
            parts.append("Existing tasks: none")
        return "\n".join(parts)

    @staticmethod
    def _extract_tool_input(response: Any) -> dict[str, Any]:
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) == "tool_use":
                data = getattr(block, "input", None)
                if isinstance(data, dict):
                    return data
        raise LLMValidationError("model did not return an emit_actions tool call")
