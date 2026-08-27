"""
Phase F (business info) -- "product vision reset" continued from Phase
D. Phase E's own payment/billing tests live in
test_subscription_checkout_billing.py; this file covers what happens
AFTER a successful payment: business info can only be submitted once a
session reaches `awaiting_business_info`; submitting it is the ONLY
thing that actually creates a Store, and it consumes the checkout
session so it can never be replayed into a second Store; the created
Store carries the theme/business info exactly, with contact_email
always the authenticated user's own account email regardless of what
the client sends; a slug collision (same company name twice) is
handled, not a 500.

`_paid_client` drives a session all the way to `awaiting_business_info`
through the REAL async Phase E flow (POST .../pay with a real card
number, which schedules `apps.subscriptions.tasks.
simulate_demo_payment_provider` via `transaction.on_commit` --
`billing.initiate_payment`'s own docstring has the full story on why
on_commit specifically, not a direct `.delay()`). Wrapped in
`TestCase.captureOnCommitCallbacks(execute=True)`, Django's own
sanctioned way to fire on_commit hooks under plain
`pytest.mark.django_db` (which never lets the real transaction commit)
-- same tool `apps/notifications/tests/conftest.py`'s
`build_confirmed_order` already uses for the identical reason.
"""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser, StoreMembership
from apps.stores.models import Store
from apps.subscriptions.models import PlanVersion, SubscriptionCheckoutSession
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

pytestmark = pytest.mark.django_db

# Smallest possible valid PNG (1x1, transparent) -- real bytes Pillow can
# actually decode, not an arbitrary blob, since Store.logo is a real
# ImageField that validates content.
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _client_for(email: str) -> APIClient:
    PlatformUser.objects.create_user(email=email, password="correct-h0rse!")  # noqa: S106
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login", {"email": email, "password": "correct-h0rse!"}, format="json"
    )
    assert login.status_code == 200, login.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


def _ready_for_payment_client(email: str) -> APIClient:
    """A client whose user already selected the real seeded Professional
    plan -- the precondition every /pay test needs."""
    client = _client_for(email)
    plan_version = PlanVersion.objects.get(plan__code="professional", is_current=True)
    start = client.post(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"theme_preset_id": None},
        format="json",
    )
    assert start.status_code == 200, start.data
    select = client.patch(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"plan_version_id": str(plan_version.id)},
        format="json",
    )
    assert select.status_code == 200, select.data
    return client


def _paid_client(email: str) -> APIClient:
    """Card number ending anything but "0002" succeeds -- see
    apps.subscriptions.billing.simulate_demo_outcome."""
    client = _ready_for_payment_client(email)
    with TestCase.captureOnCommitCallbacks(execute=True):
        pay = client.post(
            "/api/v1/subscriptions/checkout-sessions/current/pay",
            {"card_number": "4242424242424242"},
            format="json",
        )
    assert pay.status_code == 201, pay.data
    session = client.get("/api/v1/subscriptions/checkout-sessions/current")
    assert session.data["checkout_status"] == "awaiting_business_info", session.data
    return client


def test_cannot_change_plan_after_paying():
    """The other half of the same fix: widening the "open session"
    lookup must NOT let a plan be swapped out post-payment -- that would
    silently detach the price actually paid from the plan attached."""
    client = _paid_client("no-plan-swap@example.com")
    other_plan = PlanVersion.objects.get(plan__code="enterprise", is_current=True)
    response = client.patch(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"plan_version_id": str(other_plan.id)},
        format="json",
    )
    assert response.status_code == 409


def test_revisiting_the_marketplace_after_paying_updates_the_same_session_not_a_second_one():
    client = _paid_client("theme-change-after-pay@example.com")
    response = client.post(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"theme_preset_id": None},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["checkout_status"] == "awaiting_business_info"
    assert SubscriptionCheckoutSession.objects.count() == 1


# ---------------------------------------------------------------------------
# Business info: the only step that creates a real Store.
# ---------------------------------------------------------------------------


def test_business_info_requires_payment_first():
    client = _ready_for_payment_client("skips-payment@example.com")
    response = client.post(
        "/api/v1/subscriptions/checkout-sessions/current/business-info",
        {"store_name": "Skip Co", "business_category": "Retail", "contact_phone": "+966500000000"},
        format="multipart",
    )
    assert response.status_code == 409
    assert Store.objects.count() == 0


def test_business_info_creates_a_real_store_with_owner_membership():
    email = "founder@example.com"
    client = _paid_client(email)
    response = client.post(
        "/api/v1/subscriptions/checkout-sessions/current/business-info",
        {
            "store_name": "Founder's Boutique",
            "business_category": "Fashion & Apparel",
            "contact_phone": "+966511111111",
        },
        format="multipart",
    )
    assert response.status_code == 201, response.data
    store = Store.objects.get(id=response.data["id"])
    assert store.name == "Founder's Boutique"
    assert store.status == Store.Status.ACTIVE
    assert store.business_category == "Fashion & Apparel"
    assert store.contact_phone == "+966511111111"
    # contact_email is always the authenticated user's own account email.
    assert store.contact_email == email

    user = PlatformUser.objects.get(email=email)
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            membership = StoreMembership.objects.get(user=user)
        finally:
            clear_tenant_context_from_db()
    assert membership.role == StoreMembership.Role.OWNER

    session = SubscriptionCheckoutSession.objects.get(user=user)
    assert session.checkout_status == "completed"
    assert session.provisioning_status == "provisioned"
    assert session.consumed_at is not None
    assert session.store_slug_draft == store.slug


def test_business_info_carries_the_selected_theme_onto_the_store():
    """apps.subscriptions may not import apps.themes at all -- verified
    without an `apps.themes.models` import (raw SQL) AND without a
    separate physical connection (the test client's request and this
    verification both run inside the SAME `default`-alias session/
    transaction, so a genuinely separate raw connection -- like
    `_create_non_current_plan_version`'s -- would see nothing yet: this
    file's other tests never hit that because they only ever WRITE via
    a raw connection before the ORM reads, never the reverse). Still
    needs the RLS `app.current_store_id` GUC set correctly first --
    apps.tenancy is a lower layer, safe to import here."""
    email = "theme-carry@example.com"
    client = _client_for(email)

    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT id FROM themes_themepreset WHERE is_default = true LIMIT 1")
        row = cursor.fetchone()
    assert row is not None
    preset_id = row[0]

    start = client.post(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"theme_preset_id": str(preset_id)},
        format="json",
    )
    assert start.status_code == 200
    plan_version = PlanVersion.objects.get(plan__code="basic", is_current=True)
    client.patch(
        "/api/v1/subscriptions/checkout-sessions/current",
        {"plan_version_id": str(plan_version.id)},
        format="json",
    )
    with TestCase.captureOnCommitCallbacks(execute=True):
        client.post(
            "/api/v1/subscriptions/checkout-sessions/current/pay",
            {"card_number": "4242424242424242"},
            format="json",
        )

    response = client.post(
        "/api/v1/subscriptions/checkout-sessions/current/business-info",
        {
            "store_name": "Themed Store",
            "business_category": "General",
            "contact_phone": "+966522222222",
        },
        format="multipart",
    )
    assert response.status_code == 201
    store_id = response.data["id"]

    apply_tenant_context_to_db(store_id)
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute(
                "SELECT preset_id FROM themes_storethemeconfig WHERE store_id = %s", [store_id]
            )
            row = cursor.fetchone()
    finally:
        clear_tenant_context_from_db()
    assert row is not None
    assert str(row[0]) == str(preset_id)


def test_business_info_uploads_a_real_logo_image():
    client = _paid_client("logo-uploader@example.com")
    logo = SimpleUploadedFile("logo.png", _TINY_PNG, content_type="image/png")
    response = client.post(
        "/api/v1/subscriptions/checkout-sessions/current/business-info",
        {
            "store_name": "Logo Co",
            "business_category": "Retail",
            "contact_phone": "+966533333333",
            "logo": logo,
        },
        format="multipart",
    )
    assert response.status_code == 201, response.data
    store = Store.objects.get(id=response.data["id"])
    assert store.logo.name
    assert "store_logos/" in store.logo.name


def test_business_info_ignores_a_client_supplied_contact_email():
    """The serializer has no `contact_email` field at all -- a client
    trying to spoof it is simply dropped, never reaches the Store."""
    email = "real-owner@example.com"
    client = _paid_client(email)
    response = client.post(
        "/api/v1/subscriptions/checkout-sessions/current/business-info",
        {
            "store_name": "Spoof Test",
            "business_category": "Retail",
            "contact_phone": "+966544444444",
            "contact_email": "attacker@evil.example.com",
        },
        format="multipart",
    )
    assert response.status_code == 201
    store = Store.objects.get(id=response.data["id"])
    assert store.contact_email == email


def test_completed_session_cannot_be_replayed_into_a_second_store():
    client = _paid_client("no-replay@example.com")
    first = client.post(
        "/api/v1/subscriptions/checkout-sessions/current/business-info",
        {
            "store_name": "First Store",
            "business_category": "Retail",
            "contact_phone": "+966555555555",
        },
        format="multipart",
    )
    assert first.status_code == 201

    replay = client.post(
        "/api/v1/subscriptions/checkout-sessions/current/business-info",
        {
            "store_name": "Second Store",
            "business_category": "Retail",
            "contact_phone": "+966555555555",
        },
        format="multipart",
    )
    assert replay.status_code == 409
    assert Store.objects.count() == 1


def test_duplicate_company_name_gets_a_unique_slug_not_a_500():
    client_a = _paid_client("dup-a@example.com")
    response_a = client_a.post(
        "/api/v1/subscriptions/checkout-sessions/current/business-info",
        {
            "store_name": "Popular Name",
            "business_category": "Retail",
            "contact_phone": "+966566666666",
        },
        format="multipart",
    )
    assert response_a.status_code == 201

    client_b = _paid_client("dup-b@example.com")
    response_b = client_b.post(
        "/api/v1/subscriptions/checkout-sessions/current/business-info",
        {
            "store_name": "Popular Name",
            "business_category": "Retail",
            "contact_phone": "+966577777777",
        },
        format="multipart",
    )
    assert response_b.status_code == 201
    assert response_a.data["slug"] != response_b.data["slug"]
