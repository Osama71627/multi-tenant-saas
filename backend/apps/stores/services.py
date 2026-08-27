"""
Store provisioning. Kept out of views per docs/ARCHITECTURE.md section 11.

`create_store` is the ONLY place a `Store` row and its first
`StoreDomain`/`StoreMembership` come into existence together -- it owns
the whole transaction boundary. See its docstring for exactly what's
atomic and why.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import transaction

from apps.accounts.models import PlatformUser, StoreMembership
from apps.stores import hooks
from apps.stores.models import Store, StoreDomain
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

# Slugs that would collide with platform-operated subdomains or are
# reserved for future platform use. Checked case-insensitively.
RESERVED_SLUGS = frozenset(
    {
        "www",
        "api",
        "app",
        "admin",
        "dashboard",
        "platform",
        "static",
        "media",
        "assets",
        "cdn",
        "mail",
        "smtp",
        "ftp",
        "docs",
        "help",
        "support",
        "status",
        "blog",
        "store",
        "stores",
        "auth",
        "login",
        "signup",
        "register",
        "billing",
        "account",
        "accounts",
    }
)


class StoreSlugReservedError(Exception):
    pass


def create_store(
    *,
    owner: PlatformUser,
    name: str,
    slug: str,
    theme_preset_id: uuid.UUID | str | None = None,
    contact_email: str = "",
    contact_phone: str = "",
    business_category: str = "",
    logo=None,
) -> Store:
    """
    Creates a `Store`, its primary subdomain `StoreDomain`, and an
    OWNER `StoreMembership` for `owner` -- all in one transaction. If
    any step fails (most commonly: the slug/hostname is already taken,
    raising `IntegrityError` from the DB's unique constraints -- the
    authoritative guard against a race between two concurrent requests
    for the same slug, not just a pre-check), NOTHING is left behind:
    no orphaned Store without a domain or owner.

    `theme_preset_id` (Phase 12, Theme/Template decision, approved
    Option B): the merchant's chosen `ThemePreset` from the onboarding
    wizard's Choose step, if any. Forwarded to
    `apps.themes.services.provision_store_theme` via the post-creation
    hook registry (`apps.stores` never imports `apps.themes` directly --
    same layering discipline as trial-Subscription provisioning below).
    Omitting it (the default) provisions the platform's seeded default
    preset -- a Store is never left with no theme assigned, same "no
    deterministic-state gap" invariant Phase 10 established for
    entitlements.

    Deliberately does NOT require `owner.email_verified_at` to be set --
    matches the "a merchant gets a store in minutes" goal from the
    original product brief. Documented scope decision, not an oversight;
    revisit if abuse patterns show up.

    `contact_email`/`contact_phone`/`business_category`/`logo` (Phase F,
    "product vision reset" business-info step): all optional, all
    written straight onto the new `Store` row at creation time -- see
    `Store`'s own field comments for why they live there. Omitting them
    (the default) leaves the pre-Phase-F blank-safe defaults untouched,
    same as every caller before this phase (e.g. the E2E test's seeded
    stores).

    Two DB contexts on purpose within the one transaction: `Store` itself
    has no tenant context (it IS the tenant -- see apps/stores/models.py),
    but `StoreDomain`/`StoreMembership` are `TenantOwnedModel`s whose RLS
    INSERT policy requires `app.current_store_id` to already equal the
    new store's id (see docs/PHASE_1_REPORT.md / PHASE_2_REPORT.md for
    the same pattern used throughout the test suites).

    Also runs every registered post-creation hook in this SAME
    transaction (`apps.stores.hooks` -- Phase 10 registers trial
    `Subscription` provisioning there, approved architecture decision 12:
    a Store must never exist with no deterministic entitlement state).
    If a hook raises (e.g. `NoDefaultTrialPlanError`), the whole
    transaction -- Store, StoreDomain, StoreMembership included -- rolls
    back; there is no "store exists, subscription missing" state, ever.
    """
    slug = slug.lower()
    if slug in RESERVED_SLUGS:
        raise StoreSlugReservedError(f"The slug '{slug}' is reserved.")

    with transaction.atomic(using="default"):
        with tenant_context(None):
            apply_tenant_context_to_db(None)
            try:
                store = Store.objects.create(
                    name=name,
                    slug=slug,
                    status=Store.Status.ACTIVE,
                    contact_email=contact_email,
                    contact_phone=contact_phone,
                    business_category=business_category,
                    logo=logo,
                )
            finally:
                clear_tenant_context_from_db()

        with tenant_context(TenantContext(store_id=store.id)):
            apply_tenant_context_to_db(store.id)
            try:
                StoreDomain.objects.create(
                    store=store,
                    hostname=f"{slug}.{settings.PLATFORM_ROOT_DOMAIN}",
                    kind=StoreDomain.Kind.SUBDOMAIN,
                    is_primary=True,
                )
                StoreMembership.objects.create(
                    store=store,
                    user=owner,
                    role=StoreMembership.Role.OWNER,
                    status=StoreMembership.Status.ACTIVE,
                )
                hooks.run_post_creation_hooks(store=store, theme_preset_id=theme_preset_id)
            finally:
                clear_tenant_context_from_db()

    return store


def is_active_member(*, user: PlatformUser, store: Store) -> bool:
    """
    Must be called with the tenant context already set to `store.id`
    (e.g. by TenantMiddleware having resolved this request's dashboard
    path) -- `StoreMembership.objects` is tenant-scoped by design and
    raises `TenantContextMissingError` otherwise, which is the correct
    fail-closed behavior rather than silently checking the wrong store.
    """
    return StoreMembership.objects.filter(user=user, status=StoreMembership.Status.ACTIVE).exists()


def list_stores_for_user(*, user: PlatformUser) -> list[Store]:
    """
    Phase 12 (dashboard store switcher, docs/ARCHITECTURE.md section
    7.3): "which stores does THIS user belong to" is a genuinely
    cross-tenant read -- `StoreMembership` has STANDARD RLS
    (`store_id = GUC`, apps/accounts/models.py), so `.unscoped` alone
    does NOT help here: RLS is enforced at the DB role level regardless
    of the Python-side manager, and with no tenant context/GUC set at
    all, every row is invisible to every store equally (confirmed while
    building this -- the naive `.unscoped.filter(user=user)` version
    returned zero rows even for a user who genuinely has a membership).
    `apps.accounts.views.MeView`'s docstring already anticipated this
    exact gap: doing it "correctly" needs either a dedicated
    platform-level DB role or a second RLS GUC dimension layered on top
    of the per-store one -- both real architectural decisions
    deliberately not made here, in passing, inside a Phase-12 UI-plumbing
    endpoint.

    MVP-honest interim implementation instead: `Store` has an OPEN
    SELECT RLS policy (it IS the tenant root, no GUC needed to read it),
    so this loops every store's OWN tenant context and asks "is this
    user an active member here", the same per-tenant-context-loop shape
    apps.notifications.tasks.recover_unprocessed_domain_events already
    uses for an analogous "can't do this in one cross-tenant RLS query"
    problem. Correct, RLS-respecting, and safe -- but O(total stores) per
    call, not O(this user's stores). Fine at this platform's current
    scale; revisit via the deferred second-GUC-dimension architecture
    before this becomes a real cost.
    """
    member_stores: list[Store] = []
    for store in Store.objects.order_by("name").iterator():
        with tenant_context(TenantContext(store_id=store.id)):
            apply_tenant_context_to_db(store.id)
            try:
                if StoreMembership.objects.filter(
                    user=user, status=StoreMembership.Status.ACTIVE
                ).exists():
                    member_stores.append(store)
            finally:
                clear_tenant_context_from_db()
    return member_stores
