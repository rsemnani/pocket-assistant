"""Claude interpretation via the local `claude` CLI (Pro/Max subscription).

This provider runs the user's installed `claude` CLI in headless print mode
(`claude -p --output-format json`), authenticated with their Claude **subscription** — so
interpretation spends tokens they already pay for, with **no separate API bill** (unlike the
`claude` API provider in `claude.py`).

The CLI has no forced-tool-use mode in print mode, so we instruct the model to return a
single JSON object matching the action schema, then extract + validate it (Pydantic) with a
bounded repair retry. The model still only *proposes*; the backend validates and gates every
action behind approval/PIN.

Activation/deployment notes (gated, done with approval):
- The `claude` CLI must be installed and logged in with the subscription on the host that
  runs this code, and reachable from the API process (its credentials live in ~/.claude).
- Subject to the subscription's rate limits; intended for single-user/personal use.

Design references: DESIGN.md §9. The runner is injectable so tests need no real CLI.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404 - used with a fixed argv and shell=False; see _default_runner
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from pocket.core.config import Settings, get_settings
from pocket.db.enums import ActionType
from pocket.integrations.base import InterpretRequest
from pocket.integrations.claude import LLMValidationError
from pocket.schemas.actions import InterpretationResult

MAX_REPAIRS = 1

# Runner: takes the full prompt, returns the model's raw text reply.
Runner = Callable[[str], str]

_INSTRUCTIONS = f"""You are the interpretation engine for Pocket Assistant, a voice-capture
personal assistant. Decide the user's intent from the transcript and propose structured
actions.

Output rules (strict):
- Reply with ONE JSON object and nothing else. No prose, no markdown code fences.
- Shape: {{"intent": <string>, "actions": [{{"type": <string>, "explanation": <string>,
  "payload": <object>}}]}}.
- "type" must be one of: {", ".join(t.value for t in ActionType)}.
- "explanation" is a short, plain-language "what I will do".
- "payload" holds action-specific parameters (e.g. a task's title/priority).

Behavior rules:
- You ONLY propose actions; you never execute anything.
- Use the provided task context; do not invent tasks/emails/events not given.
- Only propose email/calendar actions when explicitly permitted below.
- If a coding/repo target is ambiguous, propose a single "clarify" action with options.
"""


def _default_runner(cli_path: str) -> Runner:
    def run(prompt: str) -> str:
        cmd = [cli_path, "-p", "--output-format", "json"]
        # Fixed argv, shell=False, prompt passed via stdin (never interpolated into a shell);
        # cli_path is operator-configured. Safe against command/argument injection.
        proc = subprocess.run(  # nosec B603 B607
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return proc.stdout
        if isinstance(envelope, dict) and "result" in envelope:
            return str(envelope["result"])
        return proc.stdout

    return run


def _extract_json_object(text: str) -> dict[str, Any]:
    """Pull the first balanced {...} JSON object out of arbitrary model text."""
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in model output")
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                parsed = json.loads(text[start : i + 1])
                if not isinstance(parsed, dict):
                    raise ValueError("top-level JSON is not an object")
                return parsed
    raise ValueError("unbalanced JSON object in model output")


class ClaudeCliLLM:
    name = "claude_cli"

    def __init__(self, settings: Settings | None = None, runner: Runner | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = self._settings.llm_model
        self._runner = runner or _default_runner(self._settings.claude_cli_path)

    def interpret(self, request: InterpretRequest) -> InterpretationResult:
        prompt = self._build_prompt(request)
        last_error: str | None = None

        for attempt in range(MAX_REPAIRS + 1):
            raw = self._runner(prompt)
            try:
                data = _extract_json_object(raw)
                return InterpretationResult.model_validate(
                    {**data, "model": self._model or "claude-cli"}
                )
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                if attempt >= MAX_REPAIRS:
                    break
                prompt = (
                    f"{self._build_prompt(request)}\n\n"
                    f"Your previous reply was not valid: {last_error}\n"
                    "Return ONLY a single valid JSON object as specified."
                )

        raise LLMValidationError(last_error or "invalid CLI output")

    def _build_prompt(self, request: InterpretRequest) -> str:
        parts = [
            _INSTRUCTIONS,
            "",
        ]
        if request.now:
            parts.append(
                f"Current date/time: {request.now}. Resolve relative dates "
                "(today, tomorrow, Friday) against this."
            )
        parts += [
            f"Email context permitted: {request.allow_email}",
            f"Calendar context permitted: {request.allow_calendar}",
        ]
        if request.task_context:
            parts.append(
                "Existing tasks (JSON): " + json.dumps(request.task_context, separators=(",", ":"))
            )
        else:
            parts.append("Existing tasks: none")
        parts.append("")
        parts.append(f"Transcript: {request.transcript.strip()}")
        return "\n".join(parts)
