"""Path-traversal guard for the media store."""

from __future__ import annotations

import pytest

from pocket.core.config import Settings
from pocket.media.store import MediaStore


def _store(tmp_path) -> MediaStore:
    return MediaStore(Settings(media_root=str(tmp_path)))


def test_writes_within_root(tmp_path):
    store = _store(tmp_path)
    obj = store.write("audio/2026/x.wav", b"abc")
    assert (tmp_path / "audio/2026/x.wav").read_bytes() == b"abc"
    assert obj.sha256


@pytest.mark.parametrize(
    "evil",
    [
        "../escape.txt",
        "../../etc/passwd",
        "audio/../../escape.txt",
        "/etc/passwd",
        "/abs/outside",
    ],
)
def test_rejects_traversal_and_absolute(tmp_path, evil):
    store = _store(tmp_path)
    with pytest.raises(ValueError):
        store.write(evil, b"x")
    with pytest.raises(ValueError):
        store.delete(evil)
