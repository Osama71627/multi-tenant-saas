"""
Minimal `PlatformUser` scaffold.

Deliberately introduced in Phase 1, not Phase 2, even though registration/
login/JWT flows are still Phase 2 work: Django's `AUTH_USER_MODEL` cannot
be swapped after the first `migrate` without a painful manual migration
surgery, so every real Django project defines its custom user model on
day one even if it starts nearly empty. `PlatformUser` is the "merchant /
staff / platform owner" identity realm -- see docs/ARCHITECTURE.md
section 6.1 for why it's kept separate from `Customer`, a store-scoped
identity with its own auth realm that's still deliberately unbuilt as of
Phase 6 (docs/PHASE_6_REPORT.md) -- Cart is guest/session-token-based
there on purpose, with no dependency on `Customer` existing yet.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel, TimeStampedModel
from apps.core.tokens import generate_raw_token
from apps.core.tokens import hash_raw_token as core_hash_raw_token
from apps.core.uuid7 import uuid7
from apps.tenancy.models import TenantOwnedModel


class PlatformUserManager(BaseUserManager["PlatformUser"]):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("PlatformUser requires an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_platform_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_platform_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_active", True)
        return self._create_user(email, password, **extra_fields)


class PlatformUser(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """
    Identity for the Platform Owner realm: platform staff, store owners,
    and store staff. NOT used for storefront customers -- see
    docs/ARCHITECTURE.md section 6.1 (`Customer` is a separate,
    per-store-unique identity introduced with apps.customers).
    """

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Django admin site access
    is_platform_staff = models.BooleanField(
        default=False,
        help_text="Platform Owner realm staff -- see apps.platform_admin (Phase 14).",
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)

    objects = PlatformUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # noqa: RUF012 -- matches AbstractBaseUser's own ClassVar typing

    class Meta:
        db_table = "accounts_platformuser"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.email


class PasswordResetToken(BaseModel, TimeStampedModel):
    """
    One-time password reset token. Per docs/ARCHITECTURE.md section 6.3:
    hashed in DB (never the raw token), 30-minute expiry, single-use.

    Deliberately DB-backed rather than a stateless signed token (unlike
    email verification, below): a reset token grants account takeover if
    intercepted, so it must be individually revocable/auditable, and
    "has this exact token already been used" needs a real row to check.
    """

    user = models.ForeignKey(
        "accounts.PlatformUser", on_delete=models.CASCADE, related_name="password_reset_tokens"
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_passwordresettoken"

    @staticmethod
    def hash_raw_token(raw_token: str) -> str:
        return core_hash_raw_token(raw_token)

    @classmethod
    def issue(cls, user: PlatformUser, *, ttl_minutes: int = 30) -> tuple[PasswordResetToken, str]:
        raw_token = generate_raw_token()
        instance = cls.objects.create(
            user=user,
            token_hash=cls.hash_raw_token(raw_token),
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
        )
        return instance, raw_token

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


class MfaTotpDevice(TimeStampedModel):
    """
    One TOTP device per `PlatformUser`. `secret_encrypted` uses the same
    envelope-encryption pattern as `apps.payments.encryption`
    (AES-256-GCM, versioned envelope) -- see `apps.accounts.encryption`,
    a deliberate small duplicate rather than a shared import: `accounts`
    sits below `payments` in the import-linter layering, so it can't
    depend on it.

    `confirmed_at is None` means "enrollment started but never finished
    with a correct code" -- `apps.accounts.mfa_services.enroll_start`
    freely overwrites a still-unconfirmed device (the user retried/
    rescanned a QR), but a CONFIRMED device is never silently replaced
    by that path (see `enroll_start`'s guard).
    """

    user = models.OneToOneField(
        "accounts.PlatformUser", on_delete=models.CASCADE, related_name="mfa_totp_device"
    )
    secret_encrypted = models.TextField()
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_mfatotpdevice"

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"TOTP device for {self.user_id} ({'confirmed' if self.is_confirmed else 'pending'})"


class MfaRecoveryCode(BaseModel, TimeStampedModel):
    """
    One-time backup codes, issued 8-at-a-time when a `MfaTotpDevice` is
    first confirmed. Hashed at rest -- same `core.tokens` hash-only
    pattern as `PasswordResetToken`, never the raw code. Consuming one
    (see `mfa_services.verify_recovery_code`) sets `used_at`; it is never
    deleted, so "was this code already spent" stays auditable.
    """

    user = models.ForeignKey(
        "accounts.PlatformUser", on_delete=models.CASCADE, related_name="mfa_recovery_codes"
    )
    code_hash = models.CharField(max_length=64, unique=True, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_mfarecoverycode"


class MfaChallenge(BaseModel, TimeStampedModel):
    """
    Issued the moment a platform-staff account's password check succeeds
    (`apps.accounts.views.LoginView`), before any JWT is issued -- see
    docs/PHASE_17_REPORT.md for why this is a two-step flow. Consumed by
    exactly one of: TOTP verify, recovery-code verify, or enrollment
    confirm. Same hashed-token-in-DB shape as `PasswordResetToken`
    (revocable/auditable, unlike a stateless signed token) -- see that
    model's docstring.

    `failed_attempts` caps wrong-code guesses against a single challenge
    (`MAX_ATTEMPTS`) independently of the account-level login lockout in
    `apps.accounts.lockout` -- a correct password no longer being enough
    to keep retrying TOTP codes forever.
    """

    MAX_ATTEMPTS = 5

    user = models.ForeignKey(
        "accounts.PlatformUser", on_delete=models.CASCADE, related_name="mfa_challenges"
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "accounts_mfachallenge"

    @staticmethod
    def hash_raw_token(raw_token: str) -> str:
        return core_hash_raw_token(raw_token)

    @classmethod
    def issue(cls, user: PlatformUser, *, ttl_minutes: int = 5) -> tuple[MfaChallenge, str]:
        raw_token = generate_raw_token()
        instance = cls.objects.create(
            user=user,
            token_hash=cls.hash_raw_token(raw_token),
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
        )
        return instance, raw_token

    @property
    def is_valid(self) -> bool:
        return (
            self.used_at is None
            and self.expires_at > timezone.now()
            and self.failed_attempts < self.MAX_ATTEMPTS
        )


class StoreMembership(TenantOwnedModel):
    """
    Links a `PlatformUser` to a `Store` with a role. This is the first
    real domain model built on top of `apps.tenancy.TenantOwnedModel`
    since Phase 1's `StoreDomain` -- it automatically joins the generic
    isolation test suite (backend/tests/test_tenant_isolation.py) the
    moment it's registered in apps/accounts/tests/isolation_factories.py.

    Scope note: `Role` is a fixed enum here, not a separate customizable-
    per-store `Role` table (which docs/ARCHITECTURE.md section 4.2
    sketched as a future nice-to-have -- "custom roles per store"). Five
    fixed system roles cover every real requirement so far (owner/admin/
    manager/staff/viewer), and `extra_permissions` covers "Store Staff
    permissions are customizable" from the original spec without standing
    up a whole editable-role subsystem before any domain app exists to
    actually need fine-grained permissions on. See
    apps/accounts/permissions_catalog.py.
    """

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        STAFF = "staff", "Staff"
        VIEWER = "viewer", "Viewer"

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        REMOVED = "removed", "Removed"

    user = models.ForeignKey(
        "accounts.PlatformUser", on_delete=models.CASCADE, related_name="store_memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    invited_by = models.ForeignKey(
        "accounts.PlatformUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    extra_permissions = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Permission keys granted on top of the role's base set.",
    )

    class Meta:
        db_table = "accounts_storemembership"
        constraints = [
            models.UniqueConstraint(fields=["store", "user"], name="uniq_store_membership_per_user")
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.user_id} @ {self.store_id} ({self.role})"
