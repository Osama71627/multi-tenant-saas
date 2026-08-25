"""
Envelope encryption for MFA TOTP secrets. Same AES-256-GCM, versioned-
envelope shape as `apps.payments.encryption` -- deliberately duplicated
rather than imported: `accounts` sits below `payments` in the
import-linter layering (accounts must not depend on stores/subscriptions/
catalog, and payments sits well above those), so importing from payments
here would invert the dependency graph. The master key comes from
`settings.MFA_ENCRYPTION_KEY` (env var), never the database, no KMS in
this phase -- same approved-Phase-9 posture as payment credentials.
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
        raise EncryptionError("MFA_ENCRYPTION_KEY is not valid base64") from exc
    if len(key) != 32:
        raise EncryptionError("MFA_ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256)")
    return key


def encrypt_secret(plaintext: str) -> str:
    """Returns a self-describing envelope string, safe to store in a `TextField`."""
    key = _load_key(settings.MFA_ENCRYPTION_KEY)
    nonce = os.urandom(_NONCE_LENGTH_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    version = settings.MFA_ENCRYPTION_KEY_VERSION
    nonce_b64 = base64.b64encode(nonce).decode("ascii")
    ciphertext_b64 = base64.b64encode(ciphertext).decode("ascii")
    return f"v{version}:{nonce_b64}:{ciphertext_b64}"


def decrypt_secret(envelope: str) -> str:
    try:
        version_part, nonce_b64, ciphertext_b64 = envelope.split(":", 2)
        version = int(version_part.removeprefix("v"))
    except (ValueError, AttributeError) as exc:
        raise DecryptionError("malformed ciphertext envelope") from exc

    if version != settings.MFA_ENCRYPTION_KEY_VERSION:
        raise DecryptionError(f"no key available for envelope version {version}")

    key = _load_key(settings.MFA_ENCRYPTION_KEY)
    try:
        nonce = base64.b64decode(nonce_b64, validate=True)
        ciphertext = base64.b64decode(ciphertext_b64, validate=True)
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    except (InvalidTag, ValueError):
        raise DecryptionError("failed to decrypt: invalid ciphertext or tampered data") from None
    return plaintext.decode("utf-8")
