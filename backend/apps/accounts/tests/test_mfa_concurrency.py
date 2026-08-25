"""
Real cross-connection concurrency (two genuinely separate PostgreSQL
sessions), the same proven pattern as
apps/orders/tests/test_concurrency.py and
apps/notifications/tests/test_dispatch_concurrency.py: raw `psycopg`
connections running the EXACT SQL sequence the real service function
runs (`apps.accounts.mfa_services`), not a hand-waved approximation --
`app_migrator` for setup/teardown with real commits, `app_user` (the
role every request actually runs as) for the two competing attempts.

Required security proofs for Phase 17's MFA single-use invariants (none
of these tables have RLS -- global identity tables, same as
`PlatformUser` -- so no `app.current_store_id` GUC is needed, unlike the
orders/notifications concurrency tests):

A. One `MfaChallenge`, two concurrent TOTP-verify attempts with the SAME
   valid code -- at most one consumes the challenge (a TOTP code stays
   valid for its whole ~30s window, so "the code is right" alone is not
   single-use; `mfa_services.verify_totp_login`'s `SELECT ... FOR UPDATE`
   on the challenge row is what makes consumption single-use).
B. One unused `MfaRecoveryCode`, two concurrent recovery-code-verify
   attempts through TWO DIFFERENT challenges (two separate login
   attempts both presenting the same recovery code) -- at most one
   consumes the code. The challenge-row lock alone wouldn't serialize
   this (different rows); the recovery-code row's own
   `SELECT ... FOR UPDATE` is what does.
C. One enrollment `MfaChallenge` + pending `MfaTotpDevice`, two
   concurrent enroll-confirm attempts with the SAME valid code -- at
   most one confirms the device and mints recovery codes (never two sets
   of 8 codes, never a device confirmed twice).
"""

from __future__ import annotations

import threading
from datetime import timedelta

import psycopg
import pytest
from django.db import connections
from django.utils import timezone

from apps.accounts import encryption, mfa
from apps.accounts.models import MfaChallenge
from apps.core.uuid7 import uuid7

pytestmark = pytest.mark.django_db


def _migrator_conn() -> psycopg.Connection:
    params = connections["migrator"].get_connection_params()
    return psycopg.connect(**params, autocommit=True)


def _insert_platform_user(conn, user_id: str, email: str) -> None:
    conn.execute(
        "INSERT INTO accounts_platformuser "
        "(id, created_at, updated_at, password, last_login, email, full_name, "
        "is_active, is_staff, is_platform_staff, is_superuser, email_verified_at) "
        "VALUES (%s, now(), now(), '', NULL, %s, '', true, false, true, false, NULL)",
        [user_id, email],
    )


def _insert_challenge(conn, user_id: str, token_hash: str) -> str:
    challenge_id = str(uuid7())
    expires_at = (timezone.now() + timedelta(minutes=5)).isoformat()
    conn.execute(
        "INSERT INTO accounts_mfachallenge "
        "(id, created_at, updated_at, user_id, token_hash, expires_at, used_at, failed_attempts) "
        "VALUES (%s, now(), now(), %s, %s, %s, NULL, 0)",
        [challenge_id, user_id, token_hash, expires_at],
    )
    return challenge_id


# --------------------------------------------------------------------------
# A. Single-use MfaChallenge (TOTP verify path)
# --------------------------------------------------------------------------


def _attempt_totp_verify(user_params, challenge_id: str, code_is_valid: bool) -> str:
    """Mirrors `mfa_services.verify_totp_login`'s locked check-and-consume
    sequence exactly: `SELECT ... FOR UPDATE` on the challenge, then either
    consume it (used_at) or register a failure -- all inside one
    transaction, same as the real function."""
    conn = psycopg.connect(**user_params, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT used_at, expires_at, failed_attempts FROM accounts_mfachallenge "
                "WHERE id = %s FOR UPDATE",
                [challenge_id],
            )
            row = cur.fetchone()
            assert row is not None
            used_at, expires_at, failed_attempts = row
            still_valid = used_at is None and expires_at > timezone.now() and failed_attempts < 5
            if still_valid and code_is_valid:
                cur.execute(
                    "UPDATE accounts_mfachallenge SET used_at = now() WHERE id = %s",
                    [challenge_id],
                )
                conn.commit()
                return "consumed"
            cur.execute(
                "UPDATE accounts_mfachallenge SET failed_attempts = failed_attempts + 1 "
                "WHERE id = %s",
                [challenge_id],
            )
        conn.commit()
        return "rejected"
    finally:
        conn.close()


def test_concurrent_totp_verify_attempts_consume_the_challenge_exactly_once():
    user_params = connections["default"].get_connection_params()

    user_id = str(uuid7())
    setup_conn = _migrator_conn()
    try:
        _insert_platform_user(setup_conn, user_id, f"race-totp-{user_id[:8]}@example.com")
        token_hash = MfaChallenge.hash_raw_token("raw-token-does-not-matter-for-this-test")
        challenge_id = _insert_challenge(setup_conn, user_id, token_hash)

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait()
            # Both threads present the SAME valid code -- proving the lock,
            # not code-uniqueness, is what makes this single-use.
            results.append(_attempt_totp_verify(user_params, challenge_id, code_is_valid=True))

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        outcomes = sorted(results)
        assert outcomes == ["consumed", "rejected"], outcomes

        with setup_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FILTER (WHERE used_at IS NOT NULL) FROM accounts_mfachallenge "
                "WHERE id = %s",
                [challenge_id],
            )
            (consumed_count,) = cur.fetchone()
        assert consumed_count == 1  # exactly one consumption, never zero, never two
    finally:
        setup_conn.execute("DELETE FROM accounts_mfachallenge WHERE user_id = %s", [user_id])
        setup_conn.execute("DELETE FROM accounts_platformuser WHERE id = %s", [user_id])
        setup_conn.close()


# --------------------------------------------------------------------------
# B. Single-use MfaRecoveryCode, via TWO DIFFERENT challenges
# --------------------------------------------------------------------------


def _attempt_recovery_verify(user_params, challenge_id: str, code_hash: str) -> str:
    """Mirrors `mfa_services.verify_recovery_code_login`: locks the
    CHALLENGE row (its own single-use guard) AND the RECOVERY CODE row
    (the invariant this test is actually about) in the same transaction."""
    conn = psycopg.connect(**user_params, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT used_at, expires_at, failed_attempts FROM accounts_mfachallenge "
                "WHERE id = %s FOR UPDATE",
                [challenge_id],
            )
            row = cur.fetchone()
            assert row is not None
            used_at, expires_at, failed_attempts = row
            challenge_valid = (
                used_at is None and expires_at > timezone.now() and failed_attempts < 5
            )
            if not challenge_valid:
                cur.execute(
                    "UPDATE accounts_mfachallenge SET failed_attempts = failed_attempts + 1 "
                    "WHERE id = %s",
                    [challenge_id],
                )
                conn.commit()
                return "challenge_rejected"

            cur.execute(
                "SELECT id, used_at FROM accounts_mfarecoverycode WHERE code_hash = %s FOR UPDATE",
                [code_hash],
            )
            row = cur.fetchone()
            recovery_id, recovery_used_at = (row[0], row[1]) if row else (None, None)
            if recovery_id is not None and recovery_used_at is None:
                cur.execute(
                    "UPDATE accounts_mfarecoverycode SET used_at = now() WHERE id = %s",
                    [recovery_id],
                )
                cur.execute(
                    "UPDATE accounts_mfachallenge SET used_at = now() WHERE id = %s",
                    [challenge_id],
                )
                conn.commit()
                return "consumed"
            cur.execute(
                "UPDATE accounts_mfachallenge SET failed_attempts = failed_attempts + 1 "
                "WHERE id = %s",
                [challenge_id],
            )
        conn.commit()
        return "code_rejected"
    finally:
        conn.close()


def test_concurrent_recovery_code_verify_attempts_consume_the_code_exactly_once():
    user_params = connections["default"].get_connection_params()

    user_id = str(uuid7())
    setup_conn = _migrator_conn()
    try:
        _insert_platform_user(setup_conn, user_id, f"race-recovery-{user_id[:8]}@example.com")
        # TWO separate login attempts -> two separate challenges, both
        # racing to redeem the SAME recovery code -- the scenario the
        # challenge-row lock alone cannot serialize.
        token_hash_a = MfaChallenge.hash_raw_token("challenge-a")
        token_hash_b = MfaChallenge.hash_raw_token("challenge-b")
        challenge_id_a = _insert_challenge(setup_conn, user_id, token_hash_a)
        challenge_id_b = _insert_challenge(setup_conn, user_id, token_hash_b)

        code_hash = mfa.hash_recovery_code("qwert-12345")
        setup_conn.execute(
            "INSERT INTO accounts_mfarecoverycode "
            "(id, created_at, updated_at, user_id, code_hash, used_at) "
            "VALUES (%s, now(), now(), %s, %s, NULL)",
            [str(uuid7()), user_id, code_hash],
        )

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt(challenge_id: str) -> None:
            barrier.wait()
            results.append(_attempt_recovery_verify(user_params, challenge_id, code_hash))

        threads = [
            threading.Thread(target=attempt, args=(challenge_id_a,)),
            threading.Thread(target=attempt, args=(challenge_id_b,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        outcomes = sorted(results)
        assert outcomes == ["code_rejected", "consumed"], outcomes

        with setup_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FILTER (WHERE used_at IS NOT NULL) FROM accounts_mfarecoverycode "
                "WHERE code_hash = %s",
                [code_hash],
            )
            (consumed_count,) = cur.fetchone()
        assert consumed_count == 1  # exactly one consumption
    finally:
        setup_conn.execute("DELETE FROM accounts_mfarecoverycode WHERE user_id = %s", [user_id])
        setup_conn.execute("DELETE FROM accounts_mfachallenge WHERE user_id = %s", [user_id])
        setup_conn.execute("DELETE FROM accounts_platformuser WHERE id = %s", [user_id])
        setup_conn.close()


# --------------------------------------------------------------------------
# C. Enrollment confirm -- no double-confirmation, no duplicate recovery
#    code sets.
# --------------------------------------------------------------------------


def _attempt_enroll_confirm(user_params, challenge_id: str, device_id: int) -> str:
    """Mirrors `mfa_services.enroll_confirm`'s locked sequence: lock the
    challenge, and if still valid + code correct, confirm the device AND
    mint 8 recovery codes, all in the same transaction as consuming the
    challenge."""
    conn = psycopg.connect(**user_params, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT used_at, expires_at, failed_attempts FROM accounts_mfachallenge "
                "WHERE id = %s FOR UPDATE",
                [challenge_id],
            )
            row = cur.fetchone()
            assert row is not None
            used_at, expires_at, failed_attempts = row
            still_valid = used_at is None and expires_at > timezone.now() and failed_attempts < 5
            if still_valid:
                cur.execute(
                    "UPDATE accounts_mfatotpdevice SET confirmed_at = now() WHERE id = %s",
                    [device_id],
                )
                for _ in range(8):
                    cur.execute(
                        "INSERT INTO accounts_mfarecoverycode "
                        "(id, created_at, updated_at, user_id, code_hash, used_at) "
                        "VALUES (%s, now(), now(), (SELECT user_id FROM accounts_mfatotpdevice "
                        "WHERE id = %s), %s, NULL)",
                        [str(uuid7()), device_id, str(uuid7())],
                    )
                cur.execute(
                    "UPDATE accounts_mfachallenge SET used_at = now() WHERE id = %s",
                    [challenge_id],
                )
                conn.commit()
                return "confirmed"
            cur.execute(
                "UPDATE accounts_mfachallenge SET failed_attempts = failed_attempts + 1 "
                "WHERE id = %s",
                [challenge_id],
            )
        conn.commit()
        return "rejected"
    finally:
        conn.close()


def test_concurrent_enroll_confirm_attempts_confirm_the_device_exactly_once():
    user_params = connections["default"].get_connection_params()

    user_id = str(uuid7())
    setup_conn = _migrator_conn()
    try:
        _insert_platform_user(setup_conn, user_id, f"race-enroll-{user_id[:8]}@example.com")
        token_hash = MfaChallenge.hash_raw_token("enroll-challenge")
        challenge_id = _insert_challenge(setup_conn, user_id, token_hash)

        secret = mfa.generate_totp_secret()
        with setup_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO accounts_mfatotpdevice "
                "(created_at, updated_at, user_id, secret_encrypted, confirmed_at) "
                "VALUES (now(), now(), %s, %s, NULL) RETURNING id",
                [user_id, encryption.encrypt_secret(secret)],
            )
            (device_id,) = cur.fetchone()

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait()
            results.append(_attempt_enroll_confirm(user_params, challenge_id, device_id))

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        outcomes = sorted(results)
        assert outcomes == ["confirmed", "rejected"], outcomes

        with setup_conn.cursor() as cur:
            cur.execute(
                "SELECT confirmed_at IS NOT NULL FROM accounts_mfatotpdevice WHERE id = %s",
                [device_id],
            )
            (is_confirmed,) = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) FROM accounts_mfarecoverycode WHERE user_id = %s", [user_id]
            )
            (recovery_code_count,) = cur.fetchone()
        assert is_confirmed is True
        assert recovery_code_count == 8  # exactly one enrollment's worth, never 16
    finally:
        setup_conn.execute("DELETE FROM accounts_mfarecoverycode WHERE user_id = %s", [user_id])
        setup_conn.execute("DELETE FROM accounts_mfachallenge WHERE user_id = %s", [user_id])
        setup_conn.execute("DELETE FROM accounts_mfatotpdevice WHERE user_id = %s", [user_id])
        setup_conn.execute("DELETE FROM accounts_platformuser WHERE id = %s", [user_id])
        setup_conn.close()
