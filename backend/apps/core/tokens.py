"""
Shared helper for the "generate a random opaque token, store only its
hash" pattern used anywhere a secret-bearing token needs to be looked up
later without ever persisting the raw value -- `PasswordResetToken`
(apps.accounts) and `Cart.token_hash` (apps.carts) both use this.
"""

from __future__ import annotations

import hashlib
import secrets


def generate_raw_token(*, entropy_bytes: int = 32) -> str:
    return secrets.token_urlsafe(entropy_bytes)


def hash_raw_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
