"""
Re-exports apps.orders.tests.conftest's fixtures/helpers -- standard
pytest pattern for sharing fixtures across a different test package
without a shared root conftest.py. No duplication of the real checkout-
building machinery; apps.notifications' own tests only add what's
specific to notifications itself.
"""

from django.db import transaction
from django.test import TestCase

from apps.orders.services import confirm_order
from apps.orders.tests.conftest import (  # noqa: F401 -- re-exported fixtures
    add_item_and_start_checkout,
    add_stock,
    complete_address_and_shipping,
    setup_flat_shipping,
    store_db_context,
    store_with_hostname,
    storefront_client,
    variant_in_store,
)


def build_confirmed_order(ctx, storefront_client, *, idempotency_key: str) -> dict:  # noqa: F811
    """
    Full real checkout (pending_payment) via HTTP, then confirmed
    directly through `apps.orders.services.confirm_order` -- the same
    single authoritative transition every real caller (COD/Stripe/
    manual override) goes through, without needing apps.payments'
    fixtures for tests that only care about the notification side.

    Wrapped in `TestCase.captureOnCommitCallbacks(execute=True)`
    (Django's own sanctioned tool for this, not a workaround): under
    plain `pytest.mark.django_db` (no `transaction=True` -- avoided
    project-wide because `app_user` lacks TRUNCATE, see
    apps/orders/tests/test_concurrency.py's docstring), the whole test
    runs inside ONE savepoint-based transaction that's rolled back at
    the end, so `transaction.on_commit()` callbacks registered anywhere
    during the test NEVER fire on their own -- Django only ever runs them
    on a REAL outermost commit, which this test isolation strategy
    deliberately never performs. `captureOnCommitCallbacks` is Django's
    own answer to exactly this: it manually invokes whatever got queued,
    without requiring a real commit.
    """
    from apps.orders.models import Order

    add_stock(ctx["store"], ctx["variant_id"])
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    complete_address_and_shipping(storefront_client, method["id"])
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
