"""Filesystem media store with a configurable size cap and lifecycle pruning.

Bytes live on disk under MEDIA_ROOT; metadata lives in the `media_objects` table. The store
enforces MEDIA_MAX_BYTES (default 50 GB) by pruning oldest eligible objects (audio first,
then derived; never `pinned`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pocket.core.config import Settings, get_settings

# Pruning thresholds as fractions of the cap.
_HIGH_WATER = 0.90
_LOW_WATER = 0.75

# Retention-class prune priority (lower = pruned first).
_PRUNE_ORDER = {"audio": 0, "derived": 1, "pinned": 99}


@dataclass
class StoredObject:
    path: str
    size_bytes: int
    sha256: str


class MediaStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self.root = Path(self._settings.media_root)

    def _safe_target(self, relative_path: str) -> Path:
        """Resolve a relative path inside the media root, rejecting traversal/absolute paths.

        Prevents path-traversal: a ``relative_path`` like ``../../etc/passwd`` or an absolute
        path would otherwise escape the media root. The resolved target must stay within root.
        """
        root = self.root.resolve()
        candidate = (root / relative_path).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError(f"unsafe media path: {relative_path!r}")
        return candidate

    def write(self, relative_path: str, data: bytes) -> StoredObject:
        target = self._safe_target(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return StoredObject(
            path=relative_path,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )

    def delete(self, relative_path: str) -> None:
        target = self._safe_target(relative_path)
        target.unlink(missing_ok=True)


@dataclass
class MediaRecord:
    path: str
    size_bytes: int
    retention_class: str
    created_at: datetime
    expires_at: datetime | None = None


def select_prunable(
    records: list[MediaRecord], total_bytes: int, max_bytes: int, now: datetime | None = None
) -> list[MediaRecord]:
    """Return the set of records to prune to get under the low-water mark.

    Pure function (no I/O) so it is straightforward to unit test. Honors retention order and
    expiry; never selects `pinned` objects.
    """
    now = now or datetime.now(UTC)
    if total_bytes <= max_bytes * _HIGH_WATER:
        return []

    target = int(max_bytes * _LOW_WATER)
    candidates = sorted(
        (r for r in records if r.retention_class != "pinned"),
        key=lambda r: (
            0 if (r.expires_at and r.expires_at < now) else 1,  # expired first
            _PRUNE_ORDER.get(r.retention_class, 50),
            r.created_at,
        ),
    )

    pruned: list[MediaRecord] = []
    remaining = total_bytes
    for record in candidates:
        if remaining <= target:
            break
        pruned.append(record)
        remaining -= record.size_bytes
    return pruned
