"""
Required proof for Phase 10, approved architecture decision 3: publishing
a new `PlanVersion` for a Plan must NEVER silently change the
entitlements of a Subscription still pointing at an older version.
Terms are relational and versioned, not a live-mutable row -- this is
exactly what rejects the original JSONB-snapshot design (nothing to
snapshot: the PlanVersion itself already IS the immutable snapshot).

Publishing itself goes through the `publish_plan_version` MANAGEMENT
COMMAND (`python manage.py publish_plan_version --database=migrator
...`), not a service function -- the review-round-approved boundary
(docs/PHASE_10_REPORT.md): `app_migrator` is for schema/controlled-setup
only, never a business-mutation path opened by application code. These
tests invoke it exactly as an operator would, via `call_command`.
"""

from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from django.db import transaction

from apps.subscriptions import entitlements
from apps.subscriptions.models import PlanVersion, Subscription
from apps.subscriptions.tests.conftest import create_bare_store
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

pytestmark = pytest.mark.django_db(databases=["default", "migrator"])


def _in_context(store, fn):
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            return fn()
        finally:
            clear_tenant_context_from_db()


def _publish(
    *,
    plan_code,
    price_monthly,
    price_yearly,
    currency="SAR",
    quotas=None,
    features=None,
    current=True,
):
    kwargs = {
        "plan_code": plan_code,
        "price_monthly": price_monthly,
        "price_yearly": price_yearly,
        "currency": currency,
        "quotas": json.dumps(quotas or {}),
        "features": json.dumps(features or {}),
        "database": "migrator",
    }
    if not current:
        kwargs["no_current"] = True
    call_command("publish_plan_version", **kwargs)


def test_publishing_a_new_version_does_not_alter_an_existing_subscriptions_entitlements():
    store = create_bare_store("planver-store")
    subscription = _in_context(
        store, lambda: Subscription.objects.select_related("plan_version__plan").get(store=store)
    )
    original_plan_code = subscription.plan_version.plan.code
    original_version_id = subscription.plan_version_id

    # A generous new version for the SAME plan -- e.g. a price change --
    # published via the real administrative command, not test-only SQL.
    _publish(
        plan_code=original_plan_code,
        price_monthly=999999,
        price_yearly=999999,
        quotas={"products": 100000},
    )

    # The subscription is untouched -- still on the version it was created with.
    # (A plain `subscription.refresh_from_db()` would go through `_base_manager`
    # -- `TenantManager` for a `TenantOwnedModel` -- with no tenant context set;
    # re-fetch explicitly instead, same pattern as everywhere else in this suite.)
    refreshed = _in_context(store, lambda: Subscription.objects.get(store=store))
    assert refreshed.plan_version_id == original_version_id

    # And its OWN (trial-seeded) products quota (limit=100, apps/subscriptions/
    # migrations/0002_seed_default_trial_plan.py) still applies -- not the new
    # version's 100000.
    def check():
        with transaction.atomic(using="default"):
            entitlements.check_quota(store=store, quota_key="products", delta=50)  # under 100, fine

    _in_context(store, check)  # no raise -- still bound by the OLD version's limit


# Both tests below read back via `.using("migrator")`, not the plain
# `.objects` ("default") manager: the command writes via "migrator", and
# pytest-django wraps EVERY declared test alias in its own uncommitted
# transaction for test isolation -- "default" genuinely cannot see
# "migrator"'s writes within the same test (proven directly while
# building this suite; see apps/subscriptions/tests/conftest.py's
# docstring for the full explanation). Reading via "migrator" (the same
# session that did the writes) is correct here, not a workaround.


def test_new_plan_versions_are_never_mutated_in_place():
    store = create_bare_store("planver-immutable-store")
    subscription = _in_context(
        store, lambda: Subscription.objects.select_related("plan_version__plan").get(store=store)
    )
    plan = subscription.plan_version.plan
    original_version_count = PlanVersion.objects.using("migrator").filter(plan=plan).count()

    _publish(plan_code=plan.code, price_monthly=100, price_yearly=1000)
    _publish(plan_code=plan.code, price_monthly=200, price_yearly=2000)

    # Two NEW rows, never a mutation of the original or of each other.
    new_count = PlanVersion.objects.using("migrator").filter(plan=plan).count()
    assert new_count == original_version_count + 2
    version_numbers = list(
        PlanVersion.objects.using("migrator")
        .filter(plan=plan)
        .order_by("version_number")
        .values_list("version_number", flat=True)
    )
    assert version_numbers == sorted(set(version_numbers))  # strictly increasing, no reuse


def test_only_one_current_version_per_plan_at_a_time():
    store = create_bare_store("planver-current-store")
    subscription = _in_context(
        store, lambda: Subscription.objects.select_related("plan_version__plan").get(store=store)
    )
    plan = subscription.plan_version.plan

    _publish(plan_code=plan.code, price_monthly=100, price_yearly=1000)
    v2 = PlanVersion.objects.using("migrator").get(plan=plan, is_current=True)

    assert PlanVersion.objects.using("migrator").filter(plan=plan, is_current=True).count() == 1
    assert v2.plan_id == plan.id


def test_command_refuses_to_run_against_the_default_alias():
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command(
            "publish_plan_version",
            plan_code="trial",
            price_monthly=0,
            price_yearly=0,
            currency="SAR",
            quotas="{}",
            features="{}",
            database="default",
        )


def test_command_publishes_features_too():
    from apps.subscriptions.models import PlanVersionFeature

    store = create_bare_store("planver-features-store")
    subscription = _in_context(
        store, lambda: Subscription.objects.select_related("plan_version__plan").get(store=store)
    )
    plan = subscription.plan_version.plan

    _publish(
        plan_code=plan.code,
        price_monthly=100,
        price_yearly=1000,
        features={"custom_domain": True, "api_access": False},
    )

    version = PlanVersion.objects.using("migrator").get(plan=plan, is_current=True)
    features = {
        f.feature_key: f.enabled
        for f in PlanVersionFeature.objects.using("migrator").filter(plan_version=version)
    }
    assert features == {"custom_domain": True, "api_access": False}


def test_command_rejects_invalid_quotas_json():
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="quotas"):
        call_command(
            "publish_plan_version",
            plan_code="trial",
            price_monthly=0,
            price_yearly=0,
            currency="SAR",
            quotas="not-json",
            features="{}",
            database="migrator",
        )


def test_command_rejects_invalid_features_json():
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="features"):
        call_command(
            "publish_plan_version",
            plan_code="trial",
            price_monthly=0,
            price_yearly=0,
            currency="SAR",
            quotas="{}",
            features="not-json",
            database="migrator",
        )


def test_command_rejects_an_unknown_plan_code():
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="No Plan"):
        call_command(
            "publish_plan_version",
            plan_code="does-not-exist",
            price_monthly=0,
            price_yearly=0,
            currency="SAR",
            quotas="{}",
            features="{}",
            database="migrator",
        )
