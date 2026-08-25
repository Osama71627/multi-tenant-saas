"""
Required test 6 (Phase 11 review round): Store A's event cannot render
or send using Store B's Order/template state, and Store A cannot see
Store B's NotificationDispatch rows even unscoped (RLS, not just the
Python-level TenantManager filter).
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.db import transaction
from django.test import TestCase

from apps.accounts.models import PlatformUser
from apps.core.models import EventLog
from apps.notifications.models import NotificationDispatch
from apps.notifications.tests.conftest import (
    add_item_and_start_checkout,
    add_stock,
    setup_flat_shipping,
    store_db_context,
)
from apps.orders.services import confirm_order
from apps.orders.tests.conftest import VALID_ADDRESS
from apps.stores import services as store_services
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

pytestmark = pytest.mark.django_db


def _build_confirmed_order_with_email(
    ctx, storefront_client, *, email: str, idempotency_key: str
) -> dict:
    """Same shape as `apps.notifications.tests.conftest.build_confirmed_order`,
    but with a caller-chosen checkout email -- that shared helper hardcodes
    "shopper@example.com" (via `complete_address_and_shipping`), which is
    fine for single-store tests but would make BOTH stores' orders share one
    recipient here, defeating this test's whole point."""
    from apps.orders.models import Order

    add_stock(ctx["store"], ctx["variant_id"])
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    storefront_client.post(
        "/api/v1/storefront/checkout/address",
        {"email": email, "shipping_address": VALID_ADDRESS},
        content_type="application/json",
    )
    response = storefront_client.post(
        "/api/v1/storefront/checkout/shipping",
        {"shipping_method_id": method["id"]},
        content_type="application/json",
    )
    assert response.status_code == 200, response.data
    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=idempotency_key,
    )
    assert response.status_code == 201, response.data
    order_id = response.data["id"]

    with store_db_context(ctx["store"]):
        with TestCase.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                order = Order.objects.select_for_update().get(id=order_id)
                confirm_order(order=order)
    return response.data


def _login_as(email: str, password: str = "correct-h0rse!"):  # noqa: S107
    from rest_framework.test import APIClient

    client = APIClient()
    login = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


def _build_ctx(slug: str, email: str) -> dict:
    from django.test import Client

    owner = PlatformUser.objects.create_user(email=email, password="correct-h0rse!")  # noqa: S106
    dashboard_client = _login_as(email)
    store = store_services.create_store(owner=owner, name=f"{slug} Co", slug=slug)
    hostname = f"{slug}.lvh.me"

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

    class HostPinnedClient(Client):
        def generic(self, method, path, *args, **kwargs):
            kwargs.setdefault("HTTP_HOST", hostname)
            return super().generic(method, path, *args, **kwargs)

    return {
        "store": store,
        "hostname": hostname,
        "owner": owner,
        "dashboard_client": dashboard_client,
        "variant_id": variant_id,
        "product_id": product_id,
        "price_amount": 2000,
        "storefront_client": HostPinnedClient(),
    }


def test_two_stores_confirming_orders_never_cross_contaminate_notifications():
    a = _build_ctx("notif-cross-a", "notif-cross-a-owner@example.com")
    b = _build_ctx("notif-cross-b", "notif-cross-b-owner@example.com")

    mail.outbox.clear()
    order_a = _build_confirmed_order_with_email(
        a, a["storefront_client"], email="cross-a-shopper@example.com", idempotency_key="cross-a-1"
    )
    order_b = _build_confirmed_order_with_email(
        b, b["storefront_client"], email="cross-b-shopper@example.com", idempotency_key="cross-b-1"
    )

    # Each store's dispatch/email used ONLY its own order's recipient --
    # never crossed with the other store's.
    recipients = sorted(m.to[0] for m in mail.outbox)
    assert recipients == sorted([order_a["email"], order_b["email"]])

    with store_db_context(a["store"]):
        event_a = EventLog.objects.filter(
            event_type="order.confirmed", payload__aggregate_id=order_a["id"]
        ).get()
        dispatch_a = NotificationDispatch.objects.get(event=event_a)
        assert dispatch_a.recipient == order_a["email"]
    # Store A, even unscoped, cannot see Store B's dispatch (RLS, not
    # just the Python-level TenantManager filter).
    with tenant_context(TenantContext(store_id=a["store"].id)):
        apply_tenant_context_to_db(a["store"].id)
        try:
            assert not NotificationDispatch.unscoped.filter(recipient=order_b["email"]).exists()
        finally:
            clear_tenant_context_from_db()

    with store_db_context(b["store"]):
        event_b = EventLog.objects.filter(
            event_type="order.confirmed", payload__aggregate_id=order_b["id"]
        ).get()
        dispatch_b = NotificationDispatch.objects.get(event=event_b)
        assert dispatch_b.recipient == order_b["email"]
