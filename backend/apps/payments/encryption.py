"""
Envelope encryption for provider credentials (docs/ARCHITECTURE.md section
8.3): AES-256-GCM, a fresh random 96-bit nonce per call (never reused),
authenticated (the GCM tag rejects any tampering), and a versioned text
envelope (`v<version>:<nonce_b64>:<ciphertext_b64>`) so a future key
rotation only needs to add a new `key_version -> key` lookup -- it never
needs to touch already-encrypted rows.

No KMS in this phase (approved Phase 9 decision) -- the master key comes
from `settings.PAYMENT_ENCRYPTION_KEY` (env var), never the database.

Every error path here is deliberately message-only, never including the
plaintext, the key, or the raw cryptography exception's argument (which
for `InvalidTag` is empty anyway, but this doesn't rely on that) -- "no
secrets in logs, no plaintext in exception messages" is enforced structurally,
not by convention.
"""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

_NONCE_LENGTH_BYTES = 12  # 96 bits, the standard/recommended AES-GCM nonce size


class DecryptionError(Exception):
    """Raised on any decryption failure. The message is always static/generic --
    never interpolates ciphertext, plaintext, or key material."""


class EncryptionError(Exception):
    """Raised if the configured master key is malformed (wrong length after
    base64-decoding) -- a configuration problem, not a runtime secret leak."""


def _load_key(key_b64: str) -> bytes:
    try:
        key = base64.b64decode(key_b64, validate=True)
    except Exception as exc:
        raise EncryptionError("PAYMENT_ENCRYPTION_KEY is not valid base64") from exc
    if len(key) != 32:
        raise EncryptionError("PAYMENT_ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256)")
    return key


def encrypt_secret(plaintext: str) -> str:
    """Returns a self-describing envelope string, safe to store in a `TextField`."""
    key = _load_key(settings.PAYMENT_ENCRYPTION_KEY)
    nonce = os.urandom(_NONCE_LENGTH_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    version = settings.PAYMENT_ENCRYPTION_KEY_VERSION
    nonce_b64 = base64.b64encode(nonce).decode("ascii")
    ciphertext_b64 = base64.b64encode(ciphertext).decode("ascii")
    return f"v{version}:{nonce_b64}:{ciphertext_b64}"


def decrypt_secret(envelope: str) -> str:
    try:
        version_part, nonce_b64, ciphertext_b64 = envelope.split(":", 2)
        version = int(version_part.removeprefix("v"))
    except (ValueError, AttributeError) as exc:
        raise DecryptionError("malformed ciphertext envelope") from exc

    if version != settings.PAYMENT_ENCRYPTION_KEY_VERSION:
        raise DecryptionError(f"no key available for envelope version {version}")

    key = _load_key(settings.PAYMENT_ENCRYPTION_KEY)
    try:
        nonce = base64.b64decode(nonce_b64, validate=True)
        ciphertext = base64.b64decode(ciphertext_b64, validate=True)
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    except (InvalidTag, ValueError):
        raise DecryptionError("failed to decrypt: invalid ciphertext or tampered data") from None
    return plaintext.decode("utf-8")


def mask_secret(plaintext: str, *, visible_suffix_length: int = 4) -> str:
    """Display-safe hint (docs/ARCHITECTURE.md section 8.3: "فقط last4 أو
    ••••live_9f2") -- computed once at write time and stored in plaintext
    alongside the encrypted envelope; the API never decrypts a secret just
    to redisplay part of it."""
    if len(plaintext) <= visible_suffix_length:
        return "*" * len(plaintext)
    return "*" * 4 + plaintext[-visible_suffix_length:]
