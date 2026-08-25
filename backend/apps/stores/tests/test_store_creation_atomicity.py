"""
Phase 10, approved architecture decision 12: `create_store` must never
leave a Store behind with no deterministic entitlement state. Proven
directly by making the post-creation hook fail (no seeded default trial
Plan) and checking that Store/StoreDomain/StoreMembership all roll back
together, not just the Subscription step.
"""

from __future__ import annotations

import psycopg
import pytest
from django.db import connections

from apps.accounts.models import PlatformUser, StoreMembership
from apps.stores.models import Store, StoreDomain
from apps.stores.services import create_store
from apps.subscriptions.models import Subscription
from apps.subscriptions.services import NoDefaultTrialPlanError
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

pytestmark = pytest.mark.django_db(databases=["default", "migrator"])


@pytest.fixture
def owner():
    return PlatformUser.objects.create_user(
        email="atomic-owner@example.com", password="correct-h0rse!"  # noqa: S106
    )


@pytest.fixture
def no_default_trial_plan():
    """Temporarily un-marks the seeded default trial Plan, then restores
    it -- via the migrator connection (app_user cannot write to Plan at
    all, approved architecture decision 1)."""
    migrator_params = connections["migrator"].get_connection_params()
    conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        conn.execute(
            "UPDATE subscriptions_plan SET is_default_trial = false WHERE is_default_trial = true"
        )
        yield
    finally:
        conn.execute("UPDATE subscriptions_plan SET is_default_trial = true WHERE code = 'trial'")
        conn.close()


def test_hook_failure_rolls_back_store_domain_and_membership_together(owner, no_default_trial_plan):
    with pytest.raises(NoDefaultTrialPlanError):
        create_store(owner=owner, name="Atomic Co", slug="atomic-co")

    assert not Store.objects.filter(slug="atomic-co").exists()
    assert not StoreDomain.unscoped.filter(hostname__startswith="atomic-co.").exists()
    assert not StoreMembership.unscoped.filter(user=owner).exists()


def test_store_creation_succeeds_and_provisions_a_subscription_when_the_plan_exists(owner):
    store = create_store(owner=owner, name="Atomic Ok Co", slug="atomic-ok-co")

    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            assert Subscription.objects.filter(store=store).exists()
        finally:
            clear_tenant_context_from_db()
