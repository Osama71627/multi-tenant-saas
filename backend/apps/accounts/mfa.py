"""
Pure TOTP/recovery-code primitives -- no DB, no HTTP. Kept separate from
`apps.accounts.mfa_services` (which orchestrates these against the DB
models) so the crypto/encoding logic is trivially unit-testable on its
own, same split as `apps.payments.encryption` vs `apps.payments.services`.
"""

from __future__ import annotations

import secrets

import pyotp

from apps.core.tokens import hash_raw_token

_ISSUER = "SaaS Platform Admin"
_RECOVERY_CODE_COUNT = 8
# No 0/1/i/l/o -- avoids visual ambiguity when a user copies a code by hand.
_RECOVERY_CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
_RECOVERY_CODE_GROUP_LENGTH = 5


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(*, secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=_ISSUER)


def verify_totp_code(*, secret: str, code: str) -> bool:
    code = code.strip().replace(" ", "")
    if not code.isdigit():
        return False
    # valid_window=1 tolerates the previous/next 30s step for clock drift,
    # matching every mainstream authenticator app's own tolerance.
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_recovery_codes(*, count: int = _RECOVERY_CODE_COUNT) -> list[str]:
    return [_generate_one_recovery_code() for _ in range(count)]


def _generate_one_recovery_code() -> str:
    length = _RECOVERY_CODE_GROUP_LENGTH * 2
    raw = "".join(secrets.choice(_RECOVERY_CODE_ALPHABET) for _ in range(length))
    return f"{raw[:_RECOVERY_CODE_GROUP_LENGTH]}-{raw[_RECOVERY_CODE_GROUP_LENGTH:]}"


def normalize_recovery_code(code: str) -> str:
    return code.strip().lower().replace(" ", "")


def hash_recovery_code(code: str) -> str:
    return hash_raw_token(normalize_recovery_code(code))
