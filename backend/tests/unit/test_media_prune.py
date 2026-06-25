"""Unit tests for media-store prune selection (50 GB cap lifecycle)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pocket.media.store import MediaRecord, select_prunable

NOW = datetime(2026, 6, 25, tzinfo=UTC)
CAP = 1000


def _rec(size, cls, age_days, expires=None):
    return MediaRecord(
        path=f"{cls}-{age_days}",
        size_bytes=size,
        retention_class=cls,
        created_at=NOW - timedelta(days=age_days),
        expires_at=expires,
    )


def test_no_prune_under_high_water():
    records = [_rec(100, "audio", 10)]
    assert select_prunable(records, total_bytes=100, max_bytes=CAP, now=NOW) == []


def test_prunes_audio_before_derived():
    records = [
        _rec(400, "derived", 100),
        _rec(400, "audio", 1),
        _rec(400, "audio", 50),
    ]
    pruned = select_prunable(records, total_bytes=1200, max_bytes=CAP, now=NOW)
    # Must get under low-water (750). Oldest audio pruned first.
    assert pruned[0].retention_class == "audio"
    assert sum(r.size_bytes for r in records) - sum(p.size_bytes for p in pruned) <= 750


def test_never_prunes_pinned():
    records = [_rec(1000, "pinned", 100)]
    assert select_prunable(records, total_bytes=1000, max_bytes=CAP, now=NOW) == []


def test_expired_objects_pruned_first():
    records = [
        _rec(400, "audio", 1),
        _rec(600, "audio", 1, expires=NOW - timedelta(days=1)),
    ]
    # total 1000 == cap, over the 90% high-water mark, so pruning triggers.
    pruned = select_prunable(records, total_bytes=1000, max_bytes=CAP, now=NOW)
    assert pruned and pruned[0].expires_at is not None
