"""
Direct proof that the three `StockBalance` CHECK constraints are real,
enforced by PostgreSQL itself -- the actual backstop against
overselling, independent of and even if `apps/inventory/services.py`'s
application-level checks were buggy or bypassed entirely. Bypasses the
service layer on purpose to prove the DB won't allow it either way.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.catalog.models import Product, ProductVariant
from apps.inventory.models import StockBalance, StockLocation
from apps.inventory.tests.conftest import store_db_context

pytestmark = pytest.mark.django_db


@pytest.fixture
def store_and_variant(owner_client_and_store):
    _client, _owner, store = owner_client_and_store
    with store_db_context(store):
        product = Product.objects.create(store=store, name="Check Co", slug="check-co")
        variant = ProductVariant.objects.create(
            store=store,
            product=product,
            sku="CHECK-001",
            currency="SAR",
            price_amount=1000,
            is_default=True,
        )
        location = StockLocation.objects.create(store=store, name="Check Warehouse")
    return store, variant, location


def test_on_hand_cannot_go_negative_at_the_db_level(store_and_variant):
    store, variant, location = store_and_variant
    with store_db_context(store):
        # Wraps the expected-to-fail INSERT in its own savepoint
        # (transaction.atomic()) so the IntegrityError doesn't poison
        # the outer test transaction -- without this, the store_db_context
        # cleanup below would itself fail with TransactionManagementError
        # (same pattern used throughout backend/tests/test_tenant_isolation.py).
        with pytest.raises(IntegrityError), transaction.atomic(using="default"):
            StockBalance.objects.create(
                store=store, variant=variant, location=location, quantity_on_hand=-1
            )


def test_reserved_cannot_go_negative_at_the_db_level(store_and_variant):
    store, variant, location = store_and_variant
    with store_db_context(store):
        with pytest.raises(IntegrityError), transaction.atomic(using="default"):
            StockBalance.objects.create(
                store=store,
                variant=variant,
                location=location,
                quantity_on_hand=10,
                quantity_reserved=-1,
            )


def test_reserved_cannot_exceed_on_hand_at_the_db_level(store_and_variant):
    """The exact property overselling protection relies on -- proven directly against the DB."""
    store, variant, location = store_and_variant
    with store_db_context(store):
        with pytest.raises(IntegrityError), transaction.atomic(using="default"):
            StockBalance.objects.create(
                store=store,
                variant=variant,
                location=location,
                quantity_on_hand=5,
                quantity_reserved=6,
            )
