"""
apps.stores holds the tenant *root* (`Store`) and the hostname routing
table (`StoreDomain`). Everything else a merchant configures (branding,
tax, shipping, staff...) lands here starting Phase 3 -- Phase 1 only
builds what `apps.tenancy` needs to prove the isolation mechanism against
real tables: a root to resolve into, and one genuinely tenant-owned child
table.
"""

from __future__ import annotations

from django.db import models

from apps.core.models import BaseModel, TimeStampedModel
from apps.tenancy.models import TenantOwnedModel


class Store(BaseModel, TimeStampedModel):
    """
    The tenant root. NOT a `TenantOwnedModel` -- it doesn't have a
    `store_id`, it *is* the store. Row-Level Security on this table is
    hand-written (see migrations/0001_initial.py) around `id` instead of
    `store_id`: SELECT/INSERT are open (a store's name/slug/status are not
    secret -- comparable to public DNS/whois-level information, and
    merchant registration itself must be possible for a role with no
    tenant context yet), while UPDATE/DELETE are restricted to the store's
    own context. Full platform-owner administration (suspend ANY store,
    etc.) is deferred to the platform-admin bypass role introduced later.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CLOSED = "closed", "Closed"
        # Added additively in Phase 10 (apps.subscriptions), same pattern
        # as Order.Status's Phase 9 extension -- driven by Subscription
        # lifecycle (trial/period expiry past its grace period), never by
        # a quota breach alone (approved architecture decision 11):
        # storefront browsing stays up, dashboard writes and
        # checkout/complete are rejected. See
        # apps.subscriptions.entitlements.require_active_store and
        # apps.subscriptions.tasks.apply_subscription_lifecycle_transitions.
        READ_ONLY = "read_only", "Read-only"

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=63, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    # Minimal, narrowly-scoped addition for Phase 4 (catalog pricing needs
    # an explicit currency per docs/DECISIONS.md governance point 4 --
    # "لا floating point، currency صريح في كل سجل مالي"). NOT the full
    # store-settings model (tax/shipping/locale/etc.) the original spec
    # describes -- that's still deferred to its own later phase.
    default_currency = models.CharField(max_length=3, default="SAR")
    # Phase 12 store-settings chunk: plain contact fields with an obvious
    # owner (Store itself) and no relation to any other domain -- NOT
    # wired into any other system yet (no email sending, no invoices) --
    # purely merchant-facing profile data, blank-safe additive columns
    # like default_currency above.
    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=32, blank=True, default="")
    # Business-info step (post-Phase-D "product vision reset", the
    # moment apps.themes.models's own docstring anticipated: "those
    # fields have (or will have, when the onboarding wizard needs them)
    # their authoritative home on apps.stores.models.Store, never
    # duplicated" [in apps.themes.StoreThemeConfig, which stays
    # presentation-only]). `logo` is a real uploaded file (Django
    # ImageField, local MEDIA_ROOT storage -- see config/settings/base.py)
    # -- distinct from ThemePreset.preview_image_url, which is a
    # platform-seeded reference URL, not merchant-uploaded content.
    # `business_category` is free text on purpose: no fixed taxonomy has
    # been designed yet, and forcing one now would be a bigger decision
    # than this additive column warrants.
    logo = models.ImageField(upload_to="store_logos/", blank=True, null=True)
    # `db_default` (not just `default`, unlike contact_email/contact_phone
    # above) -- real bug found running the full suite after adding this
    # column: several pre-existing tests build a `Store` row via raw SQL
    # (concurrency/platform_admin fixtures, e.g.
    # apps/orders/tests/test_concurrency.py's `_insert_store`) that lists
    # an explicit column set predating this field, so a Python-only
    # `default` (which the ORM applies, but a raw INSERT that never
    # mentions the column does not) hit this NOT NULL column with nothing
    # -- `NotNullViolation`. A real database-level DEFAULT closes that
    # gap for every future raw INSERT too, not just today's fixtures.
    business_category = models.CharField(max_length=100, blank=True, default="", db_default="")

    class Meta:
        db_table = "stores_store"
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class StoreDomain(TenantOwnedModel):
    """
    Maps a hostname (subdomain or custom domain) to its Store. This is
    the very first table `TenantMiddleware` queries on every storefront
    request, before any tenant is known -- so its SELECT policy is
    deliberately open (`USING (true)`); hostnames are public information
    (that's what DNS already is). Writes remain tenant-restricted like any
    other `TenantOwnedModel`. See migrations/0001_initial.py and
    apps/tenancy/middleware.py.
    """

    class Kind(models.TextChoices):
        SUBDOMAIN = "subdomain", "Subdomain"
        CUSTOM = "custom", "Custom domain"

    hostname = models.CharField(max_length=255, unique=True, db_index=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.SUBDOMAIN)
    is_primary = models.BooleanField(default=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "stores_storedomain"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.hostname
