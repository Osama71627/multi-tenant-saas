"""
Abstract base + managers every tenant-owned domain model uses.

This is Layer 2 of the 5-layer isolation defense described in
docs/ARCHITECTURE.md section 2.3:

  1. TenantMiddleware / TenantTask  -- resolves + publishes the context
  2. TenantManager (this file)      -- auto-filters Python-side queries
  3. DRF layer                      -- TenantPrimaryKeyRelatedField (Phase 2+)
  4. PostgreSQL Row-Level Security  -- the layer that actually matters;
                                        everything else is ergonomics
  5. Automated isolation test suite -- apps/tenancy/tests/test_isolation.py

Layer 2 existing does NOT mean layer 4 is optional. `TenantManager` filters
in Python; if a developer bypasses it with `.unscoped` or raw SQL by
mistake, RLS is what actually stops the query from returning another
store's rows. Conversely, `TenantManager` failing closed (raising instead
of silently returning an unfiltered queryset) when no tenant context is
set means a bug here shows up immediately as a loud error in tests/staging,
not as a silent leak in production.
"""

from __future__ import annotations

from django.db import models

from apps.core.models import BaseModel, TimeStampedModel
from apps.tenancy.context import get_current_store_id
from apps.tenancy.exceptions import TenantContextMissingError


class TenantQuerySet(models.QuerySet):
    def for_store(self, store_id) -> TenantQuerySet:
        return self.filter(store_id=store_id)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):  # type: ignore[misc]
    # django-stubs can't statically resolve `Manager.from_queryset(...)`'s
    # dynamically-built return type as a base class (a known limitation,
    # not a real error) -- this is Django's own officially recommended
    # pattern for attaching custom QuerySet methods to a Manager.
    """Default manager: `Model.objects` == "rows for the current tenant only"."""

    def get_queryset(self) -> TenantQuerySet:
        store_id = get_current_store_id()
        if store_id is None:
            raise TenantContextMissingError(
                f"{self.model.__name__}.objects used with no tenant context "
                "set on this request/task. If this is legitimate cross-tenant "
                f"access, use `{self.model.__name__}.unscoped` explicitly."
            )
        return super().get_queryset().filter(store_id=store_id)


class UnscopedManager(models.Manager.from_queryset(TenantQuerySet)):  # type: ignore[misc]
    """
    Explicit, greppable escape hatch for legitimate cross-tenant access
    (tenant resolution itself, platform admin, cross-store sync jobs).

    Using this manager does NOT bypass PostgreSQL RLS -- the `app_user` DB
    role still cannot see rows outside whatever the current GUC allows.
    Tables that need to be readable *before* a tenant is known (e.g.
    `StoreDomain`, to resolve the tenant from a hostname in the first
    place) get a permissive `USING (true)` SELECT policy at the DB level;
    see each app's migrations for the exact policy. `.unscoped` is simply
    the ORM-level marker that a query site is intentionally cross-tenant,
    so it's easy to audit (`grep -rn "\\.unscoped\\b"`) and easy to review.
    """

    def get_queryset(self) -> TenantQuerySet:
        return super().get_queryset()


class TenantOwnedModel(BaseModel, TimeStampedModel):
    """
    Every table that belongs to exactly one store must subclass this
    instead of `apps.core.models.BaseModel` directly.
    """

    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="+",
    )

    objects = TenantManager()
    unscoped = UnscopedManager()

    class Meta:
        abstract = True
