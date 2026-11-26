"""Token primitives for services: store token digests, never raw session tokens."""
from __future__ import annotations
import hashlib
import secrets

def generate_token() -> str:
    """Generate a cryptographically secure opaque token."""
    return secrets.token_urlsafe(32)

def token_digest(token: str) -> str:
    """Return the SHA-256 hex digest of a token for database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
