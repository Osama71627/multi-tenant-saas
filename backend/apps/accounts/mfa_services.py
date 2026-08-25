"""
MFA (TOTP) orchestration against the DB models in `apps.accounts.models`
-- pure crypto/encoding lives in `apps.accounts.mfa` and
`apps.accounts.encryption`, this module wires them to `MfaChallenge`/
`MfaTotpDevice`/`MfaRecoveryCode`.

Phase 17 approved scope (docs/PHASE_17_REPORT.md): MFA is mandatory for
every `PlatformUser` with `is_platform_staff=True` -- that flag is
already the authoritative boundary for `/api/v1/platform/*`
(`apps.platform_admin.permissions.IsPlatformStaff`), so it doubles as
the MFA-enforcement boundary; no new Owner-vs-staff role was introduced
for this. Ordinary (non-platform-staff) accounts are unaffected --
`apps.accounts.views.LoginView` only routes into this module for staff
accounts.

Two-step login (approved): a correct password never issues a JWT by
itself for a platform-staff account. It issues an `MfaChallenge`
instead; a full JWT (carrying an `mfa=True` claim -- see
`apps.accounts.tokens`) is only issued once a second factor against
that specific challenge succeeds. This is also what closes the
"promoted mid-session" gap: an access token minted before a user became
platform staff never carries `mfa=True`, so `IsPlatformStaff` (which
checks the token claim, not just the live `is_platform_staff` DB flag)
still rejects it.
"""

from __future__ import annotations

from django.db import models as django_models
from django.db import transaction
from django.utils import timezone

from apps.accounts import encryption, mfa
from apps.accounts.models import MfaChallenge, MfaRecoveryCode, MfaTotpDevice, PlatformUser


class MfaError(Exception):
    """Base for every error this module raises -- callers map these to 401."""


class InvalidChallengeError(MfaError):
    pass


class InvalidCodeError(MfaError):
    pass


class AlreadyEnrolledError(MfaError):
    pass


class NotEnrolledError(MfaError):
    pass


def check_password_credentials(*, email: str, password: str) -> PlatformUser | None:
    """Verifies email+password only -- never issues a token. Used instead of
    the full SimpleJWT serializer for platform-staff logins so no
    `OutstandingToken` row is ever created for a login that hasn't cleared
    MFA yet (see `apps.accounts.views.LoginView`)."""
    try:
        user = PlatformUser.objects.get(email__iexact=email)
    except PlatformUser.DoesNotExist:
        return None
    if not user.is_active or not user.check_password(password):
        return None
    return user


def issue_login_challenge(user: PlatformUser) -> tuple[MfaChallenge, str]:
    return MfaChallenge.issue(user)


def enrollment_state(user: PlatformUser) -> str:
    """Returns "mfa_required" (device already confirmed -- verify a code)
    or "mfa_setup_required" (no confirmed device yet -- enroll first)."""
    device = getattr(user, "mfa_totp_device", None)
    return "mfa_required" if device is not None and device.is_confirmed else "mfa_setup_required"


def _get_valid_challenge(raw_challenge_token: str, *, for_update: bool = False) -> MfaChallenge:
    """`for_update=True` locks the row (`SELECT ... FOR UPDATE`) -- required
    by every caller that goes on to CONSUME the challenge (mark it used, or
    register a failed attempt), so two concurrent requests presenting the
    same challenge_token serialize on this row instead of racing: the
    second caller's lock acquisition blocks until the first's transaction
    commits, then it re-reads the now-`used_at`-set row and correctly
    rejects it. Callers passing `for_update=True` MUST already be inside
    `transaction.atomic()` -- Django raises if not."""
    token_hash = MfaChallenge.hash_raw_token(raw_challenge_token)
    qs = MfaChallenge.objects.select_related("user")
    if for_update:
        qs = qs.select_for_update()
    try:
        challenge = qs.get(token_hash=token_hash)
    except MfaChallenge.DoesNotExist as exc:
        raise InvalidChallengeError("Challenge is invalid or has expired.") from exc
    if not challenge.is_valid:
        raise InvalidChallengeError("Challenge is invalid or has expired.")
    return challenge


def _register_challenge_failure(challenge: MfaChallenge) -> None:
    MfaChallenge.objects.filter(pk=challenge.pk).update(
        failed_attempts=django_models.F("failed_attempts") + 1
    )


def _consume_challenge(challenge: MfaChallenge) -> None:
    challenge.used_at = timezone.now()
    challenge.save(update_fields=["used_at"])


def verify_totp_login(*, raw_challenge_token: str, code: str) -> PlatformUser:
    """Locks the challenge row for the duration of the check-and-consume
    sequence (see `_get_valid_challenge`'s docstring) -- required so two
    concurrent presentations of the SAME valid TOTP code against the SAME
    challenge can't both win (a TOTP code stays valid for its whole ~30s
    window, so "the code was right" alone is not single-use; the challenge
    row's lock is what makes consumption single-use). Any exception is
    raised AFTER the `with` block, never from inside it -- raising inside
    would roll back `_register_challenge_failure`'s write along with
    everything else in the transaction, silently losing the failed-attempt
    count on every wrong code."""
    user: PlatformUser | None = None
    with transaction.atomic():
        challenge = _get_valid_challenge(raw_challenge_token, for_update=True)
        device = getattr(challenge.user, "mfa_totp_device", None)
        if device is None or not device.is_confirmed:
            raise NotEnrolledError("MFA is not enrolled for this account.")
        secret = encryption.decrypt_secret(device.secret_encrypted)
        if mfa.verify_totp_code(secret=secret, code=code):
            _consume_challenge(challenge)
            user = challenge.user
        else:
            _register_challenge_failure(challenge)
    if user is None:
        raise InvalidCodeError("Incorrect verification code.")
    return user


def verify_recovery_code_login(*, raw_challenge_token: str, code: str) -> PlatformUser:
    """Same locking discipline as `verify_totp_login`, plus a SECOND lock on
    the `MfaRecoveryCode` row itself: two concurrent logins can present the
    same recovery code through two DIFFERENT challenges (two separate
    login attempts), which the challenge-row lock alone wouldn't
    serialize -- the recovery-code row's own lock is what guarantees
    exactly-once consumption regardless of which challenge each attempt is
    using."""
    code_hash = mfa.hash_recovery_code(code)
    user: PlatformUser | None = None
    with transaction.atomic():
        challenge = _get_valid_challenge(raw_challenge_token, for_update=True)
        device = getattr(challenge.user, "mfa_totp_device", None)
        if device is None or not device.is_confirmed:
            raise NotEnrolledError("MFA is not enrolled for this account.")
        recovery_code = (
            MfaRecoveryCode.objects.select_for_update()
            .filter(user=challenge.user, code_hash=code_hash)
            .first()
        )
        if recovery_code is not None and recovery_code.used_at is None:
            recovery_code.used_at = timezone.now()
            recovery_code.save(update_fields=["used_at"])
            _consume_challenge(challenge)
            user = challenge.user
        else:
            _register_challenge_failure(challenge)
    if user is None:
        raise InvalidCodeError("Incorrect or already-used recovery code.")
    return user


def enroll_start(*, raw_challenge_token: str) -> tuple[MfaTotpDevice, str, str]:
    """Generates and stores a fresh pending secret, returning the device, the
    RAW secret (for manual key entry -- this is the only place it's ever
    available in plaintext outside `enroll_confirm`'s brief decrypt), and
    its `otpauth://` provisioning URI. Safe to call again before
    confirmation (a user who fumbled entry can just retry) -- it
    overwrites any still-unconfirmed device for this user. A CONFIRMED
    device is never silently replaced this way; that requires the
    explicit platform_admin reset action (see apps.platform_admin.services)."""
    challenge = _get_valid_challenge(raw_challenge_token)
    user = challenge.user
    existing = getattr(user, "mfa_totp_device", None)
    if existing is not None and existing.is_confirmed:
        raise AlreadyEnrolledError("MFA is already enrolled for this account.")
    secret = mfa.generate_totp_secret()
    device, _created = MfaTotpDevice.objects.update_or_create(
        user=user, defaults={"secret_encrypted": encryption.encrypt_secret(secret)}
    )
    uri = mfa.provisioning_uri(secret=secret, email=user.email)
    return device, secret, uri


def enroll_confirm(*, raw_challenge_token: str, code: str) -> tuple[PlatformUser, list[str]]:
    """Verifies the first code against the pending device, confirms it, and
    issues 8 recovery codes -- returned RAW here, exactly once; only their
    hashes are ever persisted (see `MfaRecoveryCode`). Same locked
    check-and-consume discipline as `verify_totp_login` (see its
    docstring) -- two concurrent confirms of the same enrollment challenge
    must not both succeed and both mint recovery codes."""
    result: tuple[PlatformUser, list[str]] | None = None
    with transaction.atomic():
        challenge = _get_valid_challenge(raw_challenge_token, for_update=True)
        user = challenge.user
        device = getattr(user, "mfa_totp_device", None)
        if device is None or device.is_confirmed:
            raise NotEnrolledError("No pending MFA enrollment for this account.")
        secret = encryption.decrypt_secret(device.secret_encrypted)
        if mfa.verify_totp_code(secret=secret, code=code):
            device.confirmed_at = timezone.now()
            device.save(update_fields=["confirmed_at", "updated_at"])
            raw_codes = mfa.generate_recovery_codes()
            MfaRecoveryCode.objects.bulk_create(
                [MfaRecoveryCode(user=user, code_hash=mfa.hash_recovery_code(c)) for c in raw_codes]
            )
            _consume_challenge(challenge)
            result = (user, raw_codes)
        else:
            _register_challenge_failure(challenge)
    if result is None:
        raise InvalidCodeError("Incorrect verification code.")
    return result
