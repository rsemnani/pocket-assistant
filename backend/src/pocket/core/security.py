"""Token hashing and PIN verification helpers.

Device tokens are never stored raw — only a peppered hash. The phone holds the raw token;
the server holds the hash. PIN verification (dev) compares against a configured value; in
real deployments this is replaced by a proper credential store.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_token(prefix: str = "pa") -> str:
    """Generate a high-entropy opaque token (returned to the client exactly once)."""
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def hash_token(token: str, pepper: str) -> str:
    """Return a peppered SHA-256 hash of a token for at-rest storage."""
    return hashlib.sha256(f"{pepper}:{token}".encode()).hexdigest()


def verify_token(token: str, token_hash: str, pepper: str) -> bool:
    """Constant-time comparison of a presented token against a stored hash."""
    return hmac.compare_digest(hash_token(token, pepper), token_hash)


def verify_pin(presented_pin: str, expected_pin: str) -> bool:
    """Constant-time PIN comparison (dev credential store)."""
    return hmac.compare_digest(presented_pin, expected_pin)
