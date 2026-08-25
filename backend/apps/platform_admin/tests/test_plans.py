"""
Required proof (approval section 6): Plan management preserves Phase 10
invariants -- PlanVersion terms are never mutated in place, publishing
always creates a new row, and the previous current version correctly
loses `is_current` in the same transaction.
"""

from __future__ import annotations

import pytest

from apps.platform_admin import services
from apps.platform_admin.tests.mfa_test_helpers import (
    create_and_authenticate_platform_staff as _staff_client,
)

pytestmark = pytest.mark.django_db(databases=["default", "platform"])


def test_create_plan_and_publish_first_version(make_platform_staff_user):
    actor = make_platform_staff_user("plans1@example.com")
    plan = services.create_plan(actor=actor, code="growth", name="Growth")
    assert plan.is_public is True

    version = services.publish_plan_version(
        actor=actor, plan=plan, price_monthly=5000, price_yearly=50000, currency="SAR"
    )
    assert version.version_number == 1
    assert version.is_current is True


def test_publishing_a_new_version_never_mutates_the_old_ones_terms(make_platform_staff_user):
    actor = make_platform_staff_user("plans2@example.com")
    plan = services.create_plan(actor=actor, code="scale", name="Scale")

    v1 = services.publish_plan_version(
        actor=actor, plan=plan, price_monthly=1000, price_yearly=10000
    )
    v2 = services.publish_plan_version(
        actor=actor, plan=plan, price_monthly=2000, price_yearly=20000
    )

    v1.refresh_from_db(using="platform")
    assert v1.price_monthly == 1000  # untouched
    assert v1.is_current is False  # only the bookkeeping flag flips
    assert v2.version_number == 2
    assert v2.is_current is True
    assert v2.price_monthly == 2000


def test_make_current_false_leaves_existing_current_version_alone(make_platform_staff_user):
    actor = make_platform_staff_user("plans3@example.com")
    plan = services.create_plan(actor=actor, code="draft-only", name="Draft Only")

    v1 = services.publish_plan_version(
        actor=actor, plan=plan, price_monthly=1000, price_yearly=10000
    )
    v2 = services.publish_plan_version(
        actor=actor, plan=plan, price_monthly=1500, price_yearly=15000, make_current=False
    )

    v1.refresh_from_db(using="platform")
    assert v1.is_current is True
    assert v2.is_current is False


def test_publish_creates_features_and_quotas(make_platform_staff_user):
    actor = make_platform_staff_user("plans4@example.com")
    plan = services.create_plan(actor=actor, code="featured", name="Featured")
    version = services.publish_plan_version(
        actor=actor,
        plan=plan,
        price_monthly=0,
        price_yearly=0,
        features={"api_access": True},
        quotas={"products": 50},
    )
    versions = list(services.list_plan_versions(plan=plan))
    assert len(versions) == 1
    feature_keys = {f.feature_key for f in version.features.using("platform").all()}
    quota_keys = {q.quota_key for q in version.quotas.using("platform").all()}
    assert feature_keys == {"api_access"}
    assert quota_keys == {"products"}


def test_activate_deactivate_plan_toggles_is_public(make_platform_staff_user):
    actor = make_platform_staff_user("plans5@example.com")
    plan = services.create_plan(actor=actor, code="toggle", name="Toggle")

    deactivated = services.deactivate_plan(actor=actor, plan=plan)
    assert deactivated.is_public is False

    activated = services.activate_plan(actor=actor, plan=plan)
    assert activated.is_public is True


def test_plan_lifecycle_via_http():
    client = _staff_client("plans-http@example.com")

    create_response = client.post(
        "/api/v1/platform/plans",
        {"code": "http-plan", "name": "HTTP Plan", "trial_days": 7},
        format="json",
    )
    assert create_response.status_code == 201
    plan_id = create_response.data["id"]

    publish_response = client.post(
        f"/api/v1/platform/plans/{plan_id}/versions",
        {"price_monthly": 999, "price_yearly": 9990, "currency": "SAR"},
        format="json",
    )
    assert publish_response.status_code == 201
    assert publish_response.data["version_number"] == 1
    assert publish_response.data["is_current"] is True

    detail_response = client.get(f"/api/v1/platform/plans/{plan_id}")
    assert detail_response.status_code == 200
    assert len(detail_response.data["versions"]) == 1

    deactivate_response = client.post(f"/api/v1/platform/plans/{plan_id}/deactivate")
    assert deactivate_response.status_code == 200
    assert deactivate_response.data["is_public"] is False
