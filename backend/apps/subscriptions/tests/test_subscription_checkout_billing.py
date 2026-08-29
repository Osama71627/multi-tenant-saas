"""
Phase E ("product vision reset" -- Subscription Checkout). Merchant ->
platform billing ONLY -- see apps/subscriptions/billing.py's module
docstring for the full architecture (real sandbox provider, explicit
FSM, idempotent webhook). This file is the approved spec's own
15-item test list, in order.

A note on items 11/12 ("no duplicate Subscription"/"no duplicate
Invoice"): the real `apps.subscriptions.models.Subscription`/`Invoice`
are BOTH `TenantOwnedModel` (a required, RLS-scoped `store_id`) --
`Invoice.subscription` is even a required FK to `Subscription`. Neither
can exist before a Store does, and Phase E explicitly must not create
one (item 10). So "the subscription"/"the invoice" in this phase's own
vocabulary are `SubscriptionCheckoutSession` (the in-progress
subscription-to-be) and `SubscriptionPaymentIntent` (the payment
record standing in for an invoice pre-Store) respectively -- tests
below verify uniqueness on THOSE, and item 10 separately proves the
real Store-scoped tables stay completely untouched.
"""

from __future__ import annotations

import pytest
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.stores.models import Store
from apps.subscriptions import billing
from apps.subscriptions.models import (
    Invoice,
    PlanVersion,
    Subscription,
    SubscriptionCheckoutSession,
    SubscriptionPaymentIntent,
    SubscriptionWebhookEvent,
)

pytestmark = pytest.mark.django_db

DECLINE_CARD = "4000000000000002"  # Stripe's own real published test-decline number
SUCCEED_CARD = "4242424242424242"


def _client_for(email: str, password: str = "correct-h0rse!") -> APIClient:  # noqa: S107
    PlatformUser.objects.create_user(email=email, password=password)
    client = APIClient()
    login = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    assert login.status_code == 200, login.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


def _ready_for_payment_client(email: str, plan_code: str = "professional") -> APIClient:
    client = _client_for(email)
    plan_version = PlanVersion.objects.get(plan__code=plan_code, is_current=True)
    start = client.post(
        "/api/v1/subscriptions/checkout-sessions/current", {"theme_preset_id": None}, format="json"
    )
    assert start.status_code == 200, start.data
    select = client.patch(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"plan_version_id": str(plan_version.id)},
        format="json",
    )
    assert select.status_code == 200, select.data
    return client


def _pay(client: APIClient, card_number: str = SUCCEED_CARD):
    """`billing.initiate_payment` dispatches the demo-provider task via
    `transaction.on_commit` (real bug this phase found and fixed: a
    direct `.delay()` right after the local `with transaction.atomic():`
    block still ran inside the OUTER, request-spanning transaction
    `apps.stores.middleware.TenantMiddleware` opens for every request --
    a genuinely separate Celery worker process could not see the intent
    row at all until that outer transaction really committed). Plain
    `pytest.mark.django_db` never lets that outer transaction actually
    commit (rolled back at the end of the test instead) -- Django's own
    `TestCase.captureOnCommitCallbacks(execute=True)` is the sanctioned
    way to run on_commit hooks anyway (same tool
    apps/notifications/tests/conftest.py's `build_confirmed_order`
    already uses for the identical reason on `apps.core.events.
    emit_domain_event`). By the time this returns, the response body
    reflects the state at the moment the view answered (genuinely still
    "pending" -- the task hadn't run yet), but the task itself HAS
    already run for real by then -- callers that need the resolved
    state re-fetch afterward (see the callers below)."""
    with TestCase.captureOnCommitCallbacks(execute=True):
        return client.post(
            "/api/v1/subscriptions/checkout-sessions/current/pay",
            {"card_number": card_number},
            format="json",
        )


# ---------------------------------------------------------------------------
# 1/2. Plan selection + checkout session creation (already the bulk of
# test_checkout_session_and_plans.py -- brief confirmation here in this
# phase's own context, not a duplicate suite).
# ---------------------------------------------------------------------------


def test_1_selecting_a_plan_creates_a_ready_for_payment_session():
    client = _client_for("plan-select@example.com")
    plan_version = PlanVersion.objects.get(plan__code="professional", is_current=True)
    client.post("/api/v1/subscriptions/checkout-sessions/current", {}, format="json")
    response = client.patch(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"plan_version_id": str(plan_version.id)},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["checkout_status"] == "ready_for_payment"


def test_2_checkout_session_is_created_exactly_once_and_reused():
    client = _ready_for_payment_client("session-create@example.com")
    assert SubscriptionCheckoutSession.objects.count() == 1
    # Revisiting (e.g. the marketplace) updates the SAME row.
    client.post("/api/v1/subscriptions/checkout-sessions/current", {}, format="json")
    assert SubscriptionCheckoutSession.objects.count() == 1


# ---------------------------------------------------------------------------
# 3. Payment success.
# ---------------------------------------------------------------------------


def test_3_payment_succeeds_and_session_becomes_ready_for_business_info():
    client = _ready_for_payment_client("succeeds@example.com")
    pay = _pay(client, SUCCEED_CARD)
    assert pay.status_code == 201, pay.data
    # Genuinely still "pending" in the RESPONSE BODY -- the response is
    # serialized before the on_commit-deferred task has run (see
    # _pay's docstring); the task has run for real by the time this
    # line executes, which the fresh re-fetch below actually proves.
    assert pay.data["state"] == "pending"

    session = client.get("/api/v1/subscriptions/checkout-sessions/current")
    assert session.data["checkout_status"] == "awaiting_business_info"
    assert session.data["payment_status"] == "paid"

    intent = SubscriptionPaymentIntent.objects.get(id=pay.data["id"])
    assert intent.state == "succeeded"
    assert (
        intent.amount
        == PlanVersion.objects.get(plan__code="professional", is_current=True).price_monthly
    )


# ---------------------------------------------------------------------------
# 4. Payment failure.
# ---------------------------------------------------------------------------


def test_4_payment_fails_with_the_decline_test_card():
    client = _ready_for_payment_client("declines@example.com")
    pay = _pay(client, DECLINE_CARD)
    assert pay.status_code == 201
    assert pay.data["state"] == "pending"  # see test_3's comment

    session = client.get("/api/v1/subscriptions/checkout-sessions/current")
    assert session.data["checkout_status"] == "payment_failed"
    assert session.data["payment_status"] == "failed"

    intent = SubscriptionPaymentIntent.objects.get(id=pay.data["id"])
    assert intent.failure_reason == "card_declined"


# ---------------------------------------------------------------------------
# 5. Payment retry -- same session, a NEW intent, can then succeed.
# ---------------------------------------------------------------------------


def test_5_retry_after_failure_uses_the_same_session_and_can_succeed():
    client = _ready_for_payment_client("retries@example.com")
    first = _pay(client, DECLINE_CARD)
    assert first.status_code == 201

    retry = _pay(client, SUCCEED_CARD)
    assert retry.status_code == 201, retry.data
    assert retry.data["id"] != first.data["id"]  # a NEW intent, not the failed one reused

    session_obj = SubscriptionCheckoutSession.objects.get()
    assert session_obj.checkout_status == "awaiting_business_info"
    assert SubscriptionCheckoutSession.objects.count() == 1  # same session throughout
    assert SubscriptionPaymentIntent.objects.filter(checkout_session=session_obj).count() == 2
    retry_intent = SubscriptionPaymentIntent.objects.get(id=retry.data["id"])
    assert retry_intent.state == "succeeded"


# ---------------------------------------------------------------------------
# 6. Duplicate webhook delivery.
# ---------------------------------------------------------------------------


def test_6_duplicate_webhook_delivery_is_idempotent():
    client = _ready_for_payment_client("dup-webhook@example.com")
    pay = _pay(client, SUCCEED_CARD)
    intent_id = pay.data["id"]

    # The demo task already delivered "processing" + "succeeded" once
    # (CELERY_TASK_ALWAYS_EAGER). Replay the exact same succeeded event.
    external_id = f"demo-{intent_id}-succeeded"
    before = SubscriptionWebhookEvent.objects.get(external_id=external_id)
    assert before.attempts == 1

    replay = billing.apply_payment_event(
        intent_id=intent_id, external_id=external_id, kind="payment.succeeded"
    )
    assert replay.state == "succeeded"

    after = SubscriptionWebhookEvent.objects.get(external_id=external_id)
    assert after.attempts == 2  # recorded, not reprocessed
    assert SubscriptionPaymentIntent.objects.filter(id=intent_id, state="succeeded").count() == 1


# ---------------------------------------------------------------------------
# 7. A webhook arrives AFTER payment already succeeded.
# ---------------------------------------------------------------------------


def test_7_webhook_arriving_after_already_succeeded_is_a_noop():
    client = _ready_for_payment_client("late-webhook@example.com")
    pay = _pay(client, SUCCEED_CARD)
    intent_id = pay.data["id"]
    assert SubscriptionPaymentIntent.objects.get(id=intent_id).state == "succeeded"

    # A late "failed" event for the SAME intent, different external_id
    # (a real provider would never send two different outcomes for one
    # intent, but a broken/replaying integration might) -- must not
    # flip an already-terminal, already-succeeded intent.
    late = billing.apply_payment_event(
        intent_id=intent_id, external_id=f"demo-{intent_id}-late-failed", kind="payment.failed"
    )
    assert late.state == "succeeded"  # unchanged
    session = SubscriptionCheckoutSession.objects.get()
    assert session.checkout_status == "awaiting_business_info"  # unchanged


# ---------------------------------------------------------------------------
# 8. A webhook arrives out of order (e.g. "succeeded" before "processing"
# ever ran for that intent).
# ---------------------------------------------------------------------------


def test_8_out_of_order_webhook_is_ignored_safely():
    # Build a session + a bare PENDING intent WITHOUT going through
    # /pay (so no "processing" event has been applied yet) -- exercises
    # the FSM guard directly: PENDING -> SUCCEEDED is not an allowed
    # transition (must pass through PROCESSING first).
    client = _ready_for_payment_client("out-of-order@example.com")
    user = PlatformUser.objects.get(email="out-of-order@example.com")
    session = SubscriptionCheckoutSession.objects.get(user=user)
    intent = SubscriptionPaymentIntent.objects.create(
        checkout_session=session, amount=19900, currency="SAR"
    )
    assert intent.state == "pending"

    result = billing.apply_payment_event(
        intent_id=intent.id, external_id="out-of-order-succeeded", kind="payment.succeeded"
    )
    assert result.state == "pending"  # the invalid transition was ignored, not applied

    session.refresh_from_db()
    assert session.checkout_status == "ready_for_payment"  # untouched
    del client  # unused past setup


# ---------------------------------------------------------------------------
# 9. Price can never be changed from the frontend.
# ---------------------------------------------------------------------------


def test_9_price_always_comes_from_plan_version_never_from_the_client():
    client = _ready_for_payment_client("no-price-spoof@example.com", plan_code="basic")
    real_price = PlanVersion.objects.get(plan__code="basic", is_current=True).price_monthly
    assert real_price != 1  # sanity: the seeded price isn't already this

    response = client.post(
        "/api/v1/subscriptions/checkout-sessions/current/pay",
        # InitiatePaymentSerializer has no amount/price field at all --
        # a spoofed one is simply dropped by the serializer, never
        # reaches billing.initiate_payment.
        {"card_number": SUCCEED_CARD, "amount": 1, "price": 1, "amount_minor_units": 1},
        format="json",
    )
    assert response.status_code == 201
    intent = SubscriptionPaymentIntent.objects.get(id=response.data["id"])
    assert intent.amount == real_price


# ---------------------------------------------------------------------------
# 10. No Store created after a Phase E payment success.
# ---------------------------------------------------------------------------


def test_10_no_store_created_after_payment_success():
    client = _ready_for_payment_client("no-store-yet@example.com")
    pay = _pay(client, SUCCEED_CARD)
    assert pay.status_code == 201
    assert Store.objects.count() == 0


# ---------------------------------------------------------------------------
# 11/12. No duplicate "subscription"/"invoice" -- see module docstring
# for why these map to SubscriptionCheckoutSession/SubscriptionPaymentIntent,
# not the Store-scoped Subscription/Invoice models (which structurally
# cannot exist yet -- also proven here).
# ---------------------------------------------------------------------------


def test_11_no_duplicate_checkout_session_and_no_real_subscription_row_exists():
    client = _ready_for_payment_client("no-dup-subscription@example.com")
    _pay(client, SUCCEED_CARD)
    # Retrying an already-terminal (awaiting_business_info) session
    # isn't even reachable (see billing._INITIATABLE_STATUSES) -- the
    # ONE session created for this user is the only one that ever
    # exists, regardless of how many requests are made.
    client.post("/api/v1/subscriptions/checkout-sessions/current", {}, format="json")
    assert SubscriptionCheckoutSession.objects.count() == 1
    # The real, Store-scoped Subscription model: structurally cannot
    # exist without a Store, and Phase E creates none. `.unscoped`
    # (not `.objects`) because a plain `.count()` with no tenant
    # context set at all raises TenantContextMissingError -- that
    # error IS itself further proof nothing tenant-scoped exists yet.
    assert Subscription.unscoped.count() == 0


def test_12_duplicate_webhook_never_produces_two_succeeded_payment_records():
    client = _ready_for_payment_client("no-dup-invoice@example.com")
    pay = _pay(client, SUCCEED_CARD)
    intent_id = pay.data["id"]

    for _ in range(3):
        billing.apply_payment_event(
            intent_id=intent_id,
            external_id=f"demo-{intent_id}-succeeded",  # SAME id every time
            kind="payment.succeeded",
        )
    assert SubscriptionPaymentIntent.objects.filter(state="succeeded").count() == 1
    # The real, Store-scoped Invoice model: structurally cannot exist
    # without a Subscription, which cannot exist without a Store.
    assert Invoice.unscoped.count() == 0


# ---------------------------------------------------------------------------
# 13. Demo billing is blocked in production configuration.
# ---------------------------------------------------------------------------


def test_13_demo_billing_is_refused_when_billing_mode_is_not_demo():
    client = _ready_for_payment_client("prod-blocked@example.com")
    with override_settings(SUBSCRIPTION_BILLING_MODE="live"):
        response = _pay(client, SUCCEED_CARD)
    assert response.status_code == 503
    assert SubscriptionPaymentIntent.objects.count() == 0
    session = SubscriptionCheckoutSession.objects.get()
    assert session.checkout_status == "ready_for_payment"  # untouched


def test_13b_production_settings_module_hardcodes_live_ignoring_the_environment():
    """Gate 2 of the two-gate mechanism (config/settings/base.py's
    comment): production.py must set this WITHOUT reading env() at
    all, so no deployment misconfiguration can ever leave demo billing
    reachable. Verified by reading the actual settings source, not by
    importing config.settings.production (which fails fast on missing
    required env vars by design -- see that file's own docstring)."""
    import pathlib

    production_py = (
        pathlib.Path(__file__).resolve().parents[3] / "config" / "settings" / "production.py"
    )
    source = production_py.read_text(encoding="utf-8")
    assert 'SUBSCRIPTION_BILLING_MODE = "live"' in source
    # And it must not be read from the environment on this line specifically.
    setting_line = next(
        row for row in source.splitlines() if "SUBSCRIPTION_BILLING_MODE" in row and "=" in row
    )
    assert "env(" not in setting_line


# ---------------------------------------------------------------------------
# 14. Refresh doesn't lose payment state.
# ---------------------------------------------------------------------------


def test_14_refresh_preserves_pending_and_failed_payment_state():
    client = _ready_for_payment_client("refresh-safe@example.com")

    # A fresh, independent request (simulating a page refresh) sees the
    # exact same session state at every step -- resolved by identity,
    # never by anything the client held onto.
    _pay(client, DECLINE_CARD)
    refreshed = client.get("/api/v1/subscriptions/checkout-sessions/current")
    assert refreshed.data["checkout_status"] == "payment_failed"

    _pay(client, SUCCEED_CARD)
    refreshed_again = client.get("/api/v1/subscriptions/checkout-sessions/current")
    assert refreshed_again.data["checkout_status"] == "awaiting_business_info"


# ---------------------------------------------------------------------------
# 15. Logout/login doesn't lose the user's checkout session.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Skip-payment (demo-only testing convenience, requested after Phase E
# shipped): same state machine, same idempotent apply_payment_event as a
# real payment -- just synchronous and always "succeeded", never
# reachable outside demo mode.
# ---------------------------------------------------------------------------


def test_skip_payment_reaches_awaiting_business_info_without_a_card():
    client = _ready_for_payment_client("skip-payment@example.com")
    response = client.post(
        "/api/v1/subscriptions/checkout-sessions/current/skip-payment-demo", {}, format="json"
    )
    assert response.status_code == 201, response.data
    assert response.data["state"] == "succeeded"  # resolved synchronously, unlike /pay

    session = client.get("/api/v1/subscriptions/checkout-sessions/current")
    assert session.data["checkout_status"] == "awaiting_business_info"
    assert session.data["payment_status"] == "paid"

    intent = SubscriptionPaymentIntent.objects.get(id=response.data["id"])
    assert intent.state == "succeeded"
    assert (
        intent.amount
        == PlanVersion.objects.get(plan__code="professional", is_current=True).price_monthly
    )
    # No Store, same invariant as a real payment (item 10).
    assert Store.objects.count() == 0


def test_skip_payment_goes_through_real_webhook_events_not_a_shortcut_field():
    """Proves this isn't a hand-waved status flip: the same
    SubscriptionWebhookEvent dedup ledger a real payment/webhook uses
    gets two real rows, "processing" then "succeeded"."""
    client = _ready_for_payment_client("skip-payment-events@example.com")
    response = client.post(
        "/api/v1/subscriptions/checkout-sessions/current/skip-payment-demo", {}, format="json"
    )
    intent_id = response.data["id"]
    events = SubscriptionWebhookEvent.objects.filter(intent_id=intent_id).order_by("created_at")
    assert [event.kind for event in events] == ["payment.processing", "payment.succeeded"]


def test_skip_payment_requires_a_payable_session():
    client = _client_for("skip-no-session@example.com")
    response = client.post(
        "/api/v1/subscriptions/checkout-sessions/current/skip-payment-demo", {}, format="json"
    )
    assert response.status_code == 409
    assert SubscriptionPaymentIntent.objects.count() == 0


def test_skip_payment_is_refused_when_billing_mode_is_not_demo():
    client = _ready_for_payment_client("skip-prod-blocked@example.com")
    with override_settings(SUBSCRIPTION_BILLING_MODE="live"):
        response = client.post(
            "/api/v1/subscriptions/checkout-sessions/current/skip-payment-demo", {}, format="json"
        )
    assert response.status_code == 503
    assert SubscriptionPaymentIntent.objects.count() == 0
    session = SubscriptionCheckoutSession.objects.get()
    assert session.checkout_status == "ready_for_payment"  # untouched


def test_15_logout_login_preserves_the_checkout_session():
    email = "logout-login@example.com"
    password = "correct-h0rse!"  # noqa: S105
    client = _ready_for_payment_client(email)
    _pay(client, SUCCEED_CARD)

    # A brand-new client + fresh login (never reuses the old token) --
    # the session is resolved by `request.user`, not by anything client-
    # side (models.py's own documented invariant since Phase D).
    new_client = APIClient()
    login = new_client.post(
        "/api/v1/auth/login", {"email": email, "password": password}, format="json"
    )
    assert login.status_code == 200
    new_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    response = new_client.get("/api/v1/subscriptions/checkout-sessions/current")
    assert response.status_code == 200
    assert response.data["checkout_status"] == "awaiting_business_info"
    assert SubscriptionCheckoutSession.objects.count() == 1
