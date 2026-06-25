"""Idempotency helpers.

Clients send an Idempotency-Key per resource-creating request. We persist
(key, endpoint, request_hash) -> response so replays return the original result instead of
creating duplicates (tasks, issues, calendar proposals, email searches).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def request_hash(payload: Any) -> str:
    """Stable hash of a request payload, used to detect key reuse with a different body."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()
