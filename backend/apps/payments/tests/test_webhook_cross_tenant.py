"""
Cross-tenant HTTP regression tests for the webhook route (Phase 9 review
round, required change 2): `/api/v1/webhooks/payments/<provider>/<store_id>`
is a THIRD tenant-resolution path (apps/stores/middleware.py) that generic
RLS coverage alone does not exercise -- this proves the real HTTP surface
directly, with two full stores, real Orders, real PaymentIntents, and a
signature that is cryptographically VALID for the store whose route is
being hit (so the test reaches the correlation/tenant checks, not just
the signature check).

Required invariant: zero cross-tenant side effects, regardless of what
`provider_ref`/forged metadata a payload claims, no matter which store's
route delivers it.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.payments.providers.mock import build_mock_signature_header
from apps.payments.tests.conftest import (
    create_order,
    enable_provider,
    store_db_context,
)
from apps.stores import services as store_services

pytestmark = pytest.mark.django_db


def _build_store(slug: str, email: str) -> dict:
    """Mirrors `store_with_hostname` + `variant_in_store` (conftest.py), but as a
    plain callable so a single test can build TWO independent, fully-provisioned
    stores -- pytest fixtures are cached per-test and can't be invoked twice.
    Uses `APIClient` (not plain Django `Client`) for the dashboard client --
    `setup_flat_shipping`/`enable_provider` (conftest.py) rely on DRF's `.data`
    response attribute, which plain `Client` responses don't have."""
    PlatformUser.objects.create_user(email=email, password="correct-h0rse!")  # noqa: S106
    dashboard_client = APIClient()
    login = dashboard_client.post(
        "/api/v1/auth/login", {"email": email, "password": "correct-h0rse!"}, format="json"
    )
    dashboard_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    owner = PlatformUser.objects.get(email=email)
    store = store_services.create_store(owner=owner, name=f"{slug} Co", slug=slug)
    hostname = f"{slug}.lvh.me"

    ctx = {
        "store": store,
        "hostname": hostname,
        "owner": owner,
        "dashboard_client": dashboard_client,
    }

    response = dashboard_client.post(
        f"/api/v1/dashboard/stores/{store.id}/products",
        {"name": "Widget", "slug": "widget", "sku": f"WIDGET-{slug}", "price_amount": 2000},
        format="json",
    )
    assert response.status_code == 201, response.data
    variant_id = response.data["variants"][0]["id"]
    product_id = response.data["id"]
    dashboard_client.patch(
        f"/api/v1/dashboard/stores/{store.id}/products/{product_id}",
        {"status": "active"},
        format="json",
    )
    ctx["variant_id"] = variant_id
    ctx["product_id"] = product_id

    class HostPinnedClient(Client):
        def generic(self, method, path, *args, **kwargs):
            kwargs.setdefault("HTTP_HOST", hostname)
            return super().generic(method, path, *args, **kwargs)

    ctx["storefront_client"] = HostPinnedClient()
    return ctx


def _create_order_and_intent(ctx, *, webhook_secret: str) -> dict:
    enable_provider(ctx, provider_key="mock", webhook_secret=webhook_secret)
    order = create_order(ctx, ctx["storefront_client"])
    response = ctx["storefront_client"].post(
        "/api/v1/storefront/payments/initiate",
        json.dumps({"order_id": order["id"], "provider_key": "mock"}),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=f"init-{ctx['store'].id}",
    )
    assert response.status_code == 201, response.content
    return {"order": order, "intent": response.json()}


def _webhook_url(store_id) -> str:
    return f"/api/v1/webhooks/payments/mock/{store_id}"


@pytest.fixture
def two_stores():
    store_a = _build_store("wh-tenant-a", "wh-tenant-a-owner@example.com")
    order_a = _create_order_and_intent(store_a, webhook_secret="secret-a")

    store_b = _build_store("wh-tenant-b", "wh-tenant-b-owner@example.com")
    order_b = _create_order_and_intent(store_b, webhook_secret="secret-b")

    return {"a": {**store_a, **order_a}, "b": {**store_b, **order_b}}


def _intent_state(ctx, intent_id) -> str:
    from apps.payments.models import PaymentIntent

    with store_db_context(ctx["store"]):
        return PaymentIntent.objects.get(id=intent_id).state


def _success_body(*, provider_ref: str, amount: int, forged_store_id: str) -> bytes:
    return json.dumps(
        {
            "id": f"evt_cross_{provider_ref}",
            "type": "payment_intent.succeeded",
            "data": {
                "provider_ref": provider_ref,
                "amount": amount,
                "currency": "SAR",
                # Forged metadata claiming to be about a DIFFERENT store --
                # must be structurally ignored (never read anywhere in the
                # correlation path), not merely "happen to fail" some check.
                "store_id": forged_store_id,
            },
        }
    ).encode()


def test_store_bs_provider_ref_delivered_through_store_as_route_has_no_effect(two_stores):
    """Store A's own webhook secret (cryptographically valid FOR STORE A'S ROUTE)
    signs a payload whose provider_ref belongs to Store B's PaymentIntent, plus
    forged metadata claiming store_id=B. Delivered to Store A's URL."""
    a, b = two_stores["a"], two_stores["b"]

    body = _success_body(
        provider_ref=b["intent"]["id"],
        amount=b["intent"]["amount"],
        forged_store_id=str(b["store"].id),
    )
    headers = build_mock_signature_header(body, "secret-a")  # valid for A's route

    response = a["storefront_client"].generic(
        "POST",
        _webhook_url(a["store"].id),
        data=body,
        content_type="application/json",
        **{f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()},
    )
    # The endpoint contract allows 200 (acknowledged-but-ignored, since the
    # correlation lookup legitimately finds nothing under A's tenant scope) --
    # what's required is that it produced ZERO cross-tenant effect.
    assert response.status_code in (200, 400, 404)
    assert _intent_state(b, b["intent"]["id"]) == "processing"  # Store B's intent: UNTOUCHED
    assert (
        _intent_state(a, a["intent"]["id"]) == "processing"
    )  # Store A's own intent: also untouched


def test_store_as_provider_ref_delivered_through_store_bs_route_has_no_effect(two_stores):
    """Reverse direction: Store B's own (valid-for-B) secret signs a payload
    referencing Store A's PaymentIntent, delivered to Store B's URL."""
    a, b = two_stores["a"], two_stores["b"]

    body = _success_body(
        provider_ref=a["intent"]["id"],
        amount=a["intent"]["amount"],
        forged_store_id=str(a["store"].id),
    )
    headers = build_mock_signature_header(body, "secret-b")  # valid for B's route

    response = b["storefront_client"].generic(
        "POST",
        _webhook_url(b["store"].id),
        data=body,
        content_type="application/json",
        **{f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()},
    )
    assert response.status_code in (200, 400, 404)
    assert _intent_state(a, a["intent"]["id"]) == "processing"  # Store A's intent: UNTOUCHED
    assert _intent_state(b, b["intent"]["id"]) == "processing"


def test_store_bs_secret_does_not_verify_against_store_as_route(two_stores):
    """A payload correctly signed with Store B's secret, delivered to Store A's
    route, must fail signature verification (A's route only trusts A's secret) --
    proving the two configs/secrets are genuinely independent, not just the
    correlation layer."""
    a = two_stores["a"]

    body = _success_body(
        provider_ref=a["intent"]["id"],
        amount=a["intent"]["amount"],
        forged_store_id=str(a["store"].id),
    )
    headers = build_mock_signature_header(body, "secret-b")  # signed for B, sent to A

    response = a["storefront_client"].generic(
        "POST",
        _webhook_url(a["store"].id),
        data=body,
        content_type="application/json",
        **{f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()},
    )
    assert response.status_code == 400  # signature verification fails against A's own secret
    assert _intent_state(a, a["intent"]["id"]) == "processing"
