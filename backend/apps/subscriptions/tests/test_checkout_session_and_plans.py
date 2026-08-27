"""
Phase D ("product vision reset" -- Plan Selection).

Covers exactly the acceptance criteria the phase was approved against:
plans are real/dynamic (never frontend-fabricated), a plan can be
selected, an unavailable plan cannot, price is always server-derived,
the selected theme is never lost, no Store is ever created by any of
this, a user cannot skip straight to plan selection with no session,
and there is no cross-user leakage.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest
from django.db import connections
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.core.uuid7 import uuid7
from apps.stores.models import Store
from apps.subscriptions.models import Plan, PlanVersion, SubscriptionCheckoutSession

pytestmark = pytest.mark.django_db


def _create_non_current_plan_version(*, plan: Plan) -> uuid.UUID:
    """`PlanVersion` has no `app_user` write policy at all (Phase 10,
    approved architecture decision 1) -- inserting test fixture data for
    "a version that exists but isn't offered" has to go through a raw,
    autocommit `migrator` connection, same pattern as
    apps/subscriptions/tests/conftest.py's `_publish_version_and_repoint`
    (and for the identical reason: `.using("migrator")` would still run
    inside pytest-django's own uncommitted-per-alias transaction)."""
    version_id = uuid7()
    migrator_params = connections["migrator"].get_connection_params()
    conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        conn.execute(
            "INSERT INTO subscriptions_planversion "
            "(id, created_at, updated_at, plan_id, version_number, price_monthly, "
            "price_yearly, currency, is_current, published_at) "
            "VALUES (%s, now(), now(), %s, 99, 1, 1, 'SAR', false, now())",
            [str(version_id), str(plan.id)],
        )
    finally:
        conn.close()
    return version_id


def _client_for(email: str) -> APIClient:
    PlatformUser.objects.create_user(email=email, password="correct-h0rse!")  # noqa: S106
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login", {"email": email, "password": "correct-h0rse!"}, format="json"
    )
    assert login.status_code == 200, login.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


# ---------------------------------------------------------------------------
# Public plan list: real, dynamic, never fabricated.
# ---------------------------------------------------------------------------


def test_public_plans_are_real_seeded_data_not_the_trial():
    response = APIClient().get("/api/v1/subscriptions/plans/public")
    assert response.status_code == 200
    codes = {p["plan_code"] for p in response.data}
    assert codes == {"basic", "professional", "enterprise"}
    # The auto-assigned trial plan is a different UI concern -- must
    # never appear on the customer-facing plan-selection screen.
    assert "trial" not in codes


def test_public_plans_include_real_features_and_quotas_from_the_db():
    response = APIClient().get("/api/v1/subscriptions/plans/public")
    professional = next(p for p in response.data if p["plan_code"] == "professional")
    assert professional["price_monthly"] == 19900
    assert professional["currency"] == "SAR"
    assert {"feature_key": "api_access", "enabled": True} in professional["features"]
    quota_map = {q["quota_key"]: q["limit"] for q in professional["quotas"]}
    assert quota_map["products"] == 500

    enterprise = next(p for p in response.data if p["plan_code"] == "enterprise")
    enterprise_quotas = {q["quota_key"]: q["limit"] for q in enterprise["quotas"]}
    assert enterprise_quotas["products"] is None  # unlimited


def test_plans_endpoint_needs_no_authentication():
    # A visitor must be able to see plans before registering.
    response = APIClient().get("/api/v1/subscriptions/plans/public")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Checkout session lifecycle.
# ---------------------------------------------------------------------------


def test_checkout_session_requires_authentication():
    response = APIClient().post(
        "/api/v1/subscriptions/checkout-sessions/current", {}, format="json"
    )
    assert response.status_code == 401


def test_get_current_session_is_404_before_any_session_exists():
    client = _client_for("phase-d-1@example.com")
    response = client.get("/api/v1/subscriptions/checkout-sessions/current")
    assert response.status_code == 404


def test_starting_a_session_persists_the_selected_theme():
    client = _client_for("phase-d-2@example.com")
    theme_preset_id = str(uuid.uuid4())  # opaque to this app on purpose, see models.py

    response = client.post(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"theme_preset_id": theme_preset_id},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["theme_preset_id"] == theme_preset_id
    assert response.data["checkout_status"] == "draft"
    assert response.data["plan_version"] is None

    # Survives a completely fresh request (simulates a page refresh --
    # no session id is ever sent by the client, only the auth cookie).
    again = client.get("/api/v1/subscriptions/checkout-sessions/current")
    assert again.status_code == 200
    assert again.data["theme_preset_id"] == theme_preset_id


def test_revisiting_the_marketplace_updates_the_same_session_not_a_new_one():
    client = _client_for("phase-d-3@example.com")
    first_theme = str(uuid.uuid4())
    second_theme = str(uuid.uuid4())

    client.post(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"theme_preset_id": first_theme},
        format="json",
    )
    response = client.post(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"theme_preset_id": second_theme},
        format="json",
    )
    assert response.data["theme_preset_id"] == second_theme
    assert SubscriptionCheckoutSession.objects.count() == 1


def test_selecting_a_plan_moves_session_to_ready_for_payment_with_real_price():
    client = _client_for("phase-d-4@example.com")
    client.post(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"theme_preset_id": str(uuid.uuid4())},
        format="json",
    )
    plan_version = PlanVersion.objects.select_related("plan").get(
        plan__code="professional", is_current=True
    )

    response = client.patch(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"plan_version_id": str(plan_version.id)},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["checkout_status"] == "ready_for_payment"
    assert response.data["plan_version"]["plan_code"] == "professional"
    # The price shown is whatever the server looked up, never anything
    # the client could have sent (the request body only ever carried a
    # plan_version_id -- there is no price field in SelectPlanSerializer
    # at all for a client to try to override).
    assert response.data["plan_version"]["price_monthly"] == 19900


def test_client_supplied_price_is_ignored_because_no_such_field_is_ever_read():
    client = _client_for("phase-d-5@example.com")
    client.post(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"theme_preset_id": str(uuid.uuid4())},
        format="json",
    )
    plan_version = PlanVersion.objects.get(plan__code="basic", is_current=True)
    tampered = client.patch(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"plan_version_id": str(plan_version.id), "price_monthly": 1},
        format="json",
    )
    assert tampered.status_code == 200
    # Real seeded price, not the attempted 1.
    assert tampered.data["plan_version"]["price_monthly"] == 9900


def test_cannot_select_a_plan_version_that_is_not_current():
    client = _client_for("phase-d-6@example.com")
    client.post(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"theme_preset_id": str(uuid.uuid4())},
        format="json",
    )
    plan = PlanVersion.objects.get(plan__code="basic", is_current=True).plan
    stale_version_id = _create_non_current_plan_version(plan=plan)

    response = client.patch(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"plan_version_id": str(stale_version_id)},
        format="json",
    )
    assert response.status_code == 400


def test_cannot_select_a_nonexistent_plan_version():
    client = _client_for("phase-d-7@example.com")
    client.post(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"theme_preset_id": str(uuid.uuid4())},
        format="json",
    )
    response = client.patch(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"plan_version_id": str(uuid.uuid4())},
        format="json",
    )
    assert response.status_code == 400


def test_cannot_select_a_plan_with_no_active_session_at_all():
    client = _client_for("phase-d-8@example.com")
    plan_version = PlanVersion.objects.get(plan__code="basic", is_current=True)
    response = client.patch(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"plan_version_id": str(plan_version.id)},
        format="json",
    )
    assert response.status_code == 409


def test_one_users_session_is_invisible_to_another_user():
    client_a = _client_for("phase-d-9a@example.com")
    client_b = _client_for("phase-d-9b@example.com")

    client_a.post(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"theme_preset_id": str(uuid.uuid4())},
        format="json",
    )
    # User B has started nothing -- must see their own absence of a
    # session, never user A's.
    response_b = client_b.get("/api/v1/subscriptions/checkout-sessions/current")
    assert response_b.status_code == 404


def test_selecting_a_plan_never_creates_a_store():
    """The single most important Phase D invariant: theme + plan
    selection happens entirely before any tenant exists."""
    before = Store.objects.count()
    client = _client_for("phase-d-10@example.com")
    client.post(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"theme_preset_id": str(uuid.uuid4())},
        format="json",
    )
    plan_version = PlanVersion.objects.get(plan__code="enterprise", is_current=True)
    client.patch(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"plan_version_id": str(plan_version.id)},
        format="json",
    )
    assert Store.objects.count() == before


def test_existing_store_creation_endpoint_is_unrelated_to_checkout_sessions():
    """There is no way today to reach store provisioning through a
    checkout session -- `POST /api/v1/dashboard/stores` (unchanged by
    this phase) takes no checkout_session_id and does not consult
    SubscriptionCheckoutSession at all. Phase G is where that gate
    gets built; asserting its absence now documents the boundary."""
    import inspect

    from apps.stores import services as store_services

    signature = inspect.signature(store_services.create_store)
    assert "checkout_session" not in signature.parameters
    assert "checkout_session_id" not in signature.parameters
