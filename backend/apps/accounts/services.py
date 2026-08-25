"""
Business logic for registration, email verification, and password reset.
Kept out of views/serializers per docs/ARCHITECTURE.md section 11 ("no
business logic in Views"). Every function here is plain Python callable
from a view, a management command, or a test -- no DRF/HTTP coupling.
"""

from __future__ import annotations

from django.core import signing
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired
from django.utils import timezone

from apps.accounts.models import PasswordResetToken, PlatformUser
from apps.accounts.tokens import blacklist_all_outstanding_tokens_for_user

_EMAIL_VERIFY_SALT = "accounts.email-verify"
_EMAIL_VERIFY_MAX_AGE_SECONDS = 24 * 60 * 60


class EmailVerificationError(Exception):
    pass


class PasswordResetError(Exception):
    pass


def register_user(*, email: str, password: str, full_name: str = "") -> PlatformUser:
    user = PlatformUser.objects.create_user(email=email, password=password, full_name=full_name)
    send_email_verification(user)
    return user


def send_email_verification(user: PlatformUser) -> None:
    token = signing.dumps({"user_id": str(user.id)}, salt=_EMAIL_VERIFY_SALT)
    # Plain text, sent synchronously -- deliberately NOT migrated to
    # apps.notifications (Phase 11): that phase's scope is domain-event-
    # triggered transactional email (order confirmation), not a rework of
    # this already-shipped, already-tested auth flow. Console/locmem
    # backend in dev/test, SMTP in production (config/settings/production.py).
    # (Corrected stale comment: this previously said "Phase 16", which is
    # actually Suppliers per docs/ARCHITECTURE.md's roadmap table --
    # Notifications is Phase 11.)
    send_mail(
        subject="Verify your email",
        message=f"Verification token: {token}",
        from_email=None,
        recipient_list=[user.email],
    )


def confirm_email_verification(*, token: str) -> PlatformUser:
    try:
        data = signing.loads(token, salt=_EMAIL_VERIFY_SALT, max_age=_EMAIL_VERIFY_MAX_AGE_SECONDS)
    except SignatureExpired as exc:
        raise EmailVerificationError("Verification link has expired.") from exc
    except BadSignature as exc:
        raise EmailVerificationError("Verification link is invalid.") from exc

    try:
        user = PlatformUser.objects.get(id=data["user_id"])
    except PlatformUser.DoesNotExist as exc:
        raise EmailVerificationError("Verification link is invalid.") from exc

    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    return user


def request_password_reset(*, email: str) -> None:
    """
    Deliberately silent about whether the email exists -- callers must
    always show the same "if an account exists, we sent an email"
    response regardless, to avoid leaking which emails are registered
    (user enumeration). See apps/accounts/views.py.
    """
    try:
        user = PlatformUser.objects.get(email__iexact=email)
    except PlatformUser.DoesNotExist:
        return

    _, raw_token = PasswordResetToken.issue(user)
    send_mail(
        subject="Reset your password",
        message=f"Password reset token: {raw_token}",
        from_email=None,
        recipient_list=[user.email],
    )


def confirm_password_reset(*, token: str, new_password: str) -> PlatformUser:
    token_hash = PasswordResetToken.hash_raw_token(token)
    try:
        reset_token = PasswordResetToken.objects.select_related("user").get(token_hash=token_hash)
    except PasswordResetToken.DoesNotExist as exc:
        raise PasswordResetError("Reset token is invalid.") from exc

    if not reset_token.is_valid:
        raise PasswordResetError("Reset token is invalid or has expired.")

    user = reset_token.user
    user.set_password(new_password)
    user.save(update_fields=["password"])

    reset_token.used_at = timezone.now()
    reset_token.save(update_fields=["used_at"])

    # A password reset is a strong signal to invalidate every other
    # active session too -- see docs/ARCHITECTURE.md section 6.3
    # ("يُبطل كل الجلسات"). Reuses the same bulk-blacklist mechanism as
    # refresh-token-family invalidation.
    blacklist_all_outstanding_tokens_for_user(user.id)
    return user
