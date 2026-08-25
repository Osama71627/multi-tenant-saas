"""Pure unit tests for apps.accounts.mfa -- no DB needed."""

from __future__ import annotations

import pyotp

from apps.accounts import mfa


def test_generate_totp_secret_is_a_valid_base32_secret():
    secret = mfa.generate_totp_secret()
    # pyotp.TOTP construction itself validates base32-ness; a code can be
    # generated from it without raising.
    assert pyotp.TOTP(secret).now().isdigit()


def test_verify_totp_code_accepts_the_current_code():
    secret = mfa.generate_totp_secret()
    code = pyotp.TOTP(secret).now()
    assert mfa.verify_totp_code(secret=secret, code=code) is True


def test_verify_totp_code_rejects_a_wrong_code():
    secret = mfa.generate_totp_secret()
    assert mfa.verify_totp_code(secret=secret, code="000000") is False


def test_verify_totp_code_rejects_non_digit_input():
    secret = mfa.generate_totp_secret()
    assert mfa.verify_totp_code(secret=secret, code="not-a-code") is False


def test_provisioning_uri_embeds_issuer_and_account():
    secret = mfa.generate_totp_secret()
    uri = mfa.provisioning_uri(secret=secret, email="owner@example.com")
    assert uri.startswith("otpauth://totp/")
    assert "owner%40example.com" in uri or "owner@example.com" in uri


def test_generate_recovery_codes_returns_the_requested_count_all_unique():
    codes = mfa.generate_recovery_codes(count=8)
    assert len(codes) == 8
    assert len(set(codes)) == 8
    for code in codes:
        assert "-" in code


def test_hash_recovery_code_is_deterministic_and_case_insensitive():
    assert mfa.hash_recovery_code("abcde-12345") == mfa.hash_recovery_code("ABCDE-12345")


def test_hash_recovery_code_ignores_surrounding_whitespace():
    assert mfa.hash_recovery_code("abcde-12345") == mfa.hash_recovery_code("  abcde-12345  ")
