"""Structured JSON logging with secret/transcript redaction by construction.

Transcript text, email bodies, and raw LLM I/O must never be logged. We log identifiers
(capture_id, action_id, device_id) and reference the sensitive content by ID instead. A
defensive redaction processor strips known-sensitive keys if they ever slip through.
"""

from __future__ import annotations

import logging
from typing import cast

import structlog
from structlog.typing import EventDict, WrappedLogger

# Keys whose values are sensitive and must never appear in logs.
_REDACT_KEYS = frozenset(
    {
        "transcript",
        "transcript_raw",
        "transcript_edited",
        "body",
        "email_body",
        "pin",
        "token",
        "device_token",
        "api_key",
        "authorization",
        "password",
        "llm_input",
        "llm_output",
        "ics_feed_url",
    }
)

_REDACTED = "***redacted***"


def _redact(_logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
    for key in list(event_dict.keys()):
        if key.lower() in _REDACT_KEYS:
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog to emit redacted JSON lines."""
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
