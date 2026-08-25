"""
The Phase 5 DoD from docs/ARCHITECTURE.md's roadmap: "اختبار التزامن
يمر — لا بيع زائد" (a concurrency test passes -- no overselling). This
is the single most important test in this phase.

Real cross-connection concurrency (two genuinely separate PostgreSQL
sessions), not a sequential simulation -- same reasoning and same
proven pattern as
apps/catalog/tests/test_variant_options.py::test_concurrent_inserts_with_the_same_option_signature_only_one_succeeds
(docs/PHASE_4_REPORT.md section 5.2): `pytest.mark.django_db(transaction=True)`
is avoided because its teardown needs `TRUNCATE`, which `app_user`
deliberately does not have (RLS-bypassing, by design -- see
docs/PHASE_3_REPORT.md's role model). Raw `psycopg` connections instead:

  * `migrator` (the schema OWNER) to seed Store/Product/ProductVariant/
    StockLocation/StockBalance rows directly -- PostgreSQL exempts a
    table's owner from its own RLS policies by default, so this needs
    no tenant-context GUC dance, and cleanup is a plain `DELETE FROM
    stores_store` (cascades everything via `on_delete=CASCADE`), which
    `app_migrator` can always do regardless of `app_user`'s privileges.
  * `app_user` (the real, RLS-restricted role) for the actual competing
    reservation attempts -- each connection runs the EXACT sequence
    `apps/inventory/services.py:reserve_stock` runs: `SELECT ... FOR
    UPDATE`, an availability check, then `UPDATE`, all in one
    transaction. This proves the real locking strategy, not just the
    underlying constraint mechanism (already proven generically in
    Phase 4).
"""

from __future__ import annotations

import threading
import uuid

import psycopg
import pytest
from django.db import connections

pytestmark = pytest.mark.django_db


def _reserve_via_select_for_update(user_params, balance_id: str, store_id: str, want: int) -> str:
    """The exact sequence apps/inventory/services.py:reserve_stock runs, in raw SQL."""
    conn = psycopg.connect(**user_params, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_store_id', %s, true)", [store_id])
            cur.execute(
                "SELECT quantity_on_hand, quantity_reserved FROM inventory_stockbalance "
                "WHERE id = %s FOR UPDATE",
                [balance_id],
            )
            row = cur.fetchone()
            assert row is not None
            on_hand, reserved = row
            available = on_hand - reserved
            if available < want:
                conn.rollback()
                return "rejected"
            cur.execute(
                "UPDATE inventory_stockbalance SET quantity_reserved = quantity_reserved + %s "
                "WHERE id = %s",
                [want, balance_id],
            )
        conn.commit()
        return "reserved"
    finally:
        conn.close()


def test_two_concurrent_reservations_exceeding_on_hand_never_both_succeed():
    migrator_params = connections["migrator"].get_connection_params()
    user_params = connections["default"].get_connection_params()

    store_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    variant_id = str(uuid.uuid4())
    location_id = str(uuid.uuid4())
    balance_id = str(uuid.uuid4())

    setup_conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        setup_conn.execute(
            "INSERT INTO stores_store "
            "(id, created_at, updated_at, name, slug, status, default_currency, "
            "contact_email, contact_phone) "
            "VALUES (%s, now(), now(), 'Race Co', %s, 'active', 'SAR', '', '')",
            [store_id, f"race-co-{store_id[:8]}"],
        )
        setup_conn.execute(
            "INSERT INTO catalog_product "
            "(id, created_at, updated_at, name, slug, description, status, seo_title, "
            "seo_description, store_id) "
            "VALUES (%s, now(), now(), 'Race Widget', %s, '', 'draft', '', '', %s)",
            [product_id, f"race-widget-{product_id[:8]}", store_id],
        )
        setup_conn.execute(
            "INSERT INTO catalog_productvariant "
            "(id, created_at, updated_at, sku, status, is_default, position, currency, "
            "price_amount, barcode, option_signature, product_id, store_id) "
            "VALUES (%s, now(), now(), %s, 'active', true, 0, 'SAR', 1000, '', '{}', %s, %s)",
            [variant_id, f"RACE-{variant_id[:8]}", product_id, store_id],
        )
        setup_conn.execute(
            "INSERT INTO inventory_stocklocation "
            "(id, created_at, updated_at, name, is_active, store_id) "
            "VALUES (%s, now(), now(), 'Race Warehouse', true, %s)",
            [location_id, store_id],
        )
        # The scenario: 10 on hand. Two threads each try to reserve 6
        # (12 total) -- at most one can succeed.
        setup_conn.execute(
            "INSERT INTO inventory_stockbalance "
            "(id, created_at, updated_at, quantity_on_hand, quantity_reserved, store_id, "
            "variant_id, location_id) "
            "VALUES (%s, now(), now(), 10, 0, %s, %s, %s)",
            [balance_id, store_id, variant_id, location_id],
        )

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait()
            results.append(_reserve_via_select_for_update(user_params, balance_id, store_id, 6))

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(results) == ["rejected", "reserved"], results

        with setup_conn.cursor() as cur:
            cur.execute(
                "SELECT quantity_on_hand, quantity_reserved "
                "FROM inventory_stockbalance WHERE id = %s",
                [balance_id],
            )
            row = cur.fetchone()
            assert row is not None
            on_hand, reserved = row

        assert on_hand == 10
        assert reserved == 6  # only ONE reservation of 6 went through, never 12
        assert reserved <= on_hand  # the actual "no overselling" property
    finally:
        # Django's `on_delete=CASCADE` is application-level (the ORM
        # issues explicit child deletes), NOT a DB-level `ON DELETE
        # CASCADE` constraint (confirmed: `confdeltype = 'a'`/NO ACTION
        # on these FKs) -- raw SQL here must delete children before the
        # parent itself, in dependency order.
        setup_conn.execute("DELETE FROM inventory_stockbalance WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM inventory_stocklocation WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM catalog_productvariant WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM catalog_product WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM stores_store WHERE id = %s", [store_id])
        setup_conn.close()
