"""
Real cross-connection concurrency (two genuinely separate PostgreSQL
sessions), the same proven pattern as
apps/inventory/tests/test_overselling_concurrency.py (Phase 5) and
docs/PHASE_4_REPORT.md section 5.2: `pytest.mark.django_db(transaction=True)`
is avoided because its teardown needs `TRUNCATE`, which `app_user`
deliberately does not have. Raw `psycopg` connections instead:
`app_migrator` (RLS-exempt table owner) for setup/teardown with real
commits, `app_user` (the actual RLS-restricted role every request runs
as) for the competing attempts -- each running the EXACT SQL sequence
the real service function runs, not a hand-waved approximation.

These are the invariants approved for Phase 8 (docs/PHASE_8_REPORT.md
decision 15, plus 2 more required by the Phase 8 review round) -- no
concurrency tests beyond these real, invariant-backed ones:

1. Last inventory unit, two different Orders competing for it.
2. Same `Idempotency-Key`, two concurrent `checkout/complete` attempts.
3. A coupon's last available use, two concurrent checkouts.
4. `OrderNumberSequence` under two concurrent checkouts for the same Store.
5. Single-order-per-`CheckoutSession`, two concurrent `complete` attempts
   on the SAME session with DIFFERENT Idempotency-Keys (the review round
   flagged that invariant #2 alone only rules out reusing the SAME key --
   this is the one that proves a session can't yield two Orders).
"""

from __future__ import annotations

import json
import threading
import uuid

import psycopg
import pytest
from django.db import connections

from apps.core.uuid7 import uuid7

pytestmark = pytest.mark.django_db


def _insert_store(conn, store_id: str, slug: str) -> None:
    conn.execute(
        "INSERT INTO stores_store "
        "(id, created_at, updated_at, name, slug, status, default_currency, "
        "contact_email, contact_phone) "
        "VALUES (%s, now(), now(), 'Race Co', %s, 'active', 'SAR', '', '')",
        [store_id, slug],
    )


# --------------------------------------------------------------------------
# 1. Last inventory unit -- two different Orders, same reservation contract
#    apps/orders/services.py:_reserve_item_stock actually uses
#    (`order_reservation_reference`). The underlying lock mechanism
#    (`SELECT ... FOR UPDATE` on `StockBalance`) is the same one proven in
#    Phase 5 -- this test proves it holds under the Phase 8 reference
#    contract, not a second independent proof of the same primitive.
# --------------------------------------------------------------------------


def _reserve_for_order(
    user_params, balance_id: str, store_id: str, order_id: str, want: int
) -> str:
    """The exact sequence `apps.inventory.services.reserve_stock` runs, in raw SQL,
    using the Phase 8 `order:<uuid>` reference contract."""
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
            if on_hand - reserved < want:
                conn.rollback()
                return "rejected"
            cur.execute(
                "UPDATE inventory_stockbalance SET quantity_reserved = quantity_reserved + %s "
                "WHERE id = %s",
                [want, balance_id],
            )
            cur.execute(
                "INSERT INTO inventory_stockreservation "
                "(id, created_at, updated_at, quantity, reference, status, "
                "store_id, variant_id, location_id) "
                "VALUES (%s, now(), now(), %s, %s, 'active', %s, "
                "(SELECT variant_id FROM inventory_stockbalance WHERE id = %s), "
                "(SELECT location_id FROM inventory_stockbalance WHERE id = %s))",
                [str(uuid7()), want, f"order:{order_id}", store_id, balance_id, balance_id],
            )
        conn.commit()
        return "reserved"
    finally:
        conn.close()


def test_two_orders_racing_for_the_last_inventory_unit_only_one_wins():
    migrator_params = connections["migrator"].get_connection_params()
    user_params = connections["default"].get_connection_params()

    store_id, product_id, variant_id, location_id, balance_id = (str(uuid7()) for _ in range(5))
    order_a_id, order_b_id = str(uuid7()), str(uuid7())

    setup_conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        _insert_store(setup_conn, store_id, f"race-{store_id[:8]}")
        setup_conn.execute(
            "INSERT INTO catalog_product "
            "(id, created_at, updated_at, name, slug, description, status, "
            "seo_title, seo_description, store_id) "
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
        # Exactly 1 unit on hand -- two Orders each want 1. At most one wins.
        setup_conn.execute(
            "INSERT INTO inventory_stockbalance "
            "(id, created_at, updated_at, quantity_on_hand, quantity_reserved, "
            "store_id, variant_id, location_id) "
            "VALUES (%s, now(), now(), 1, 0, %s, %s, %s)",
            [balance_id, store_id, variant_id, location_id],
        )

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt(order_id: str) -> None:
            barrier.wait()
            results.append(_reserve_for_order(user_params, balance_id, store_id, order_id, 1))

        threads = [
            threading.Thread(target=attempt, args=(order_a_id,)),
            threading.Thread(target=attempt, args=(order_b_id,)),
        ]
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
            on_hand, reserved = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) FROM inventory_stockreservation WHERE reference IN (%s, %s)",
                [f"order:{order_a_id}", f"order:{order_b_id}"],
            )
            (reservation_count,) = cur.fetchone()

        assert on_hand == 1
        assert reserved == 1  # only ONE order's reservation of 1 went through, never 2
        assert reservation_count == 1  # no partial/orphaned reservation for the loser
    finally:
        setup_conn.execute("DELETE FROM inventory_stockreservation WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM inventory_stockbalance WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM inventory_stocklocation WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM catalog_productvariant WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM catalog_product WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM stores_store WHERE id = %s", [store_id])
        setup_conn.close()


# --------------------------------------------------------------------------
# 2. Same Idempotency-Key, concurrent `checkout/complete` attempts -- the
#    exact `try: INSERT ... except unique violation: SELECT existing` shape
#    `apps.orders.services.checkout_complete` runs, proving Postgres's
#    unique-index insert blocking really does serialize two concurrent
#    claims down to exactly one winner (see that function's docstring).
# --------------------------------------------------------------------------


def _claim_or_replay(
    user_params, store_id: str, key: str, fingerprint: str, body: dict
) -> tuple[str, dict | None]:
    conn = psycopg.connect(**user_params, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_store_id', %s, true)", [store_id])
            try:
                cur.execute(
                    "INSERT INTO orders_idempotencykey "
                    "(id, created_at, updated_at, store_id, key, request_fingerprint, status, "
                    "response_status, response_body) "
                    "VALUES (%s, now(), now(), %s, %s, %s, 'pending', NULL, NULL)",
                    [str(uuid7()), store_id, key, fingerprint],
                )
            except psycopg.errors.UniqueViolation:
                # `set_config(..., true)` is transaction-LOCAL -- the rollback that
                # unwinds the failed INSERT also clears it, so it must be re-set for
                # the new implicit transaction the next statement starts, or RLS sees
                # no tenant context and the SELECT below returns zero rows.
                conn.rollback()
                cur.execute("SELECT set_config('app.current_store_id', %s, true)", [store_id])
                cur.execute(
                    "SELECT status, response_body FROM orders_idempotencykey "
                    "WHERE store_id = %s AND key = %s",
                    [store_id, key],
                )
                row = cur.fetchone()
                assert row is not None
                status_value, response_body = row
                conn.commit()
                return "replayed", json.loads(response_body)

            # Simulate the real work `_build_order` does, then complete the claim --
            # all still inside the SAME transaction as the INSERT above, exactly like
            # `checkout_complete`.
            cur.execute(
                "UPDATE orders_idempotencykey SET status = 'completed', response_status = 201, "
                "response_body = %s WHERE store_id = %s AND key = %s",
                [json.dumps(body), store_id, key],
            )
        conn.commit()
        return "created", body
    finally:
        conn.close()


def test_same_idempotency_key_concurrent_requests_yield_exactly_one_order():
    migrator_params = connections["migrator"].get_connection_params()
    user_params = connections["default"].get_connection_params()

    store_id = str(uuid7())
    key = f"idem-{uuid.uuid4()}"
    fingerprint = "fixed-fingerprint"
    body = {"order_number": "ORD-RACE-000001"}

    setup_conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        _insert_store(setup_conn, store_id, f"idem-{store_id[:8]}")

        results: list[tuple[str, dict | None]] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait()
            results.append(_claim_or_replay(user_params, store_id, key, fingerprint, body))

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        outcomes = sorted(r[0] for r in results)
        assert outcomes == ["created", "replayed"], outcomes
        # Both responses must be identical -- the replay is a REPLAY, not a second Order.
        assert results[0][1] == results[1][1] == body

        with setup_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*), COUNT(*) FILTER (WHERE status = 'completed') "
                "FROM orders_idempotencykey WHERE store_id = %s AND key = %s",
                [store_id, key],
            )
            total, completed = cur.fetchone()
        assert (total, completed) == (1, 1)  # exactly one row, exactly one completion
    finally:
        setup_conn.execute("DELETE FROM orders_idempotencykey WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM stores_store WHERE id = %s", [store_id])
        setup_conn.close()


# --------------------------------------------------------------------------
# 3. Coupon last-use -- usage_limit=1, times_used=0, two concurrent
#    checkouts. Exact lock sequence `apps.orders.services._build_order`
#    runs on the coupon: `SELECT ... FOR UPDATE`, re-validate, increment.
# --------------------------------------------------------------------------


def _consume_coupon(user_params, coupon_id: str, store_id: str) -> str:
    conn = psycopg.connect(**user_params, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_store_id', %s, true)", [store_id])
            cur.execute(
                "SELECT times_used, usage_limit FROM pricing_coupon WHERE id = %s FOR UPDATE",
                [coupon_id],
            )
            row = cur.fetchone()
            assert row is not None
            times_used, usage_limit = row
            if usage_limit is not None and times_used >= usage_limit:
                conn.rollback()
                return "rejected"
            cur.execute(
                "UPDATE pricing_coupon SET times_used = times_used + 1 WHERE id = %s", [coupon_id]
            )
        conn.commit()
        return "consumed"
    finally:
        conn.close()


def test_two_checkouts_racing_for_a_coupons_last_use_only_one_consumes_it():
    migrator_params = connections["migrator"].get_connection_params()
    user_params = connections["default"].get_connection_params()

    store_id, coupon_id = str(uuid7()), str(uuid7())

    setup_conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        _insert_store(setup_conn, store_id, f"coupon-race-{store_id[:8]}")
        setup_conn.execute(
            "INSERT INTO pricing_coupon "
            "(id, created_at, updated_at, code, kind, percentage_value, fixed_amount_value, "
            "currency, is_active, usage_limit, times_used, store_id) "
            "VALUES (%s, now(), now(), 'LASTUSE', 'percentage', 10, NULL, '', true, 1, 0, %s)",
            [coupon_id, store_id],
        )

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait()
            results.append(_consume_coupon(user_params, coupon_id, store_id))

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(results) == ["consumed", "rejected"], results

        with setup_conn.cursor() as cur:
            cur.execute("SELECT times_used FROM pricing_coupon WHERE id = %s", [coupon_id])
            (times_used,) = cur.fetchone()
        assert times_used == 1  # only ONE of the two racing checkouts consumed it
    finally:
        setup_conn.execute("DELETE FROM pricing_coupon WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM stores_store WHERE id = %s", [store_id])
        setup_conn.close()


# --------------------------------------------------------------------------
# 4. OrderNumberSequence -- a shared per-store counter. Two different,
#    both-succeeding checkouts for the SAME store must never collide on a
#    number or lose an increment. Exact lock sequence
#    `apps.orders.services._next_order_number` runs: `SELECT ... FOR
#    UPDATE` on the one sequence row, increment, save -- all inside the
#    same transaction as the rest of `_build_order`.
# --------------------------------------------------------------------------


def _allocate_order_number(user_params, sequence_id: str, store_id: str) -> int:
    conn = psycopg.connect(**user_params, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_store_id', %s, true)", [store_id])
            cur.execute(
                "SELECT last_number FROM orders_ordernumbersequence WHERE id = %s FOR UPDATE",
                [sequence_id],
            )
            row = cur.fetchone()
            assert row is not None
            (last_number,) = row
            next_number = last_number + 1
            cur.execute(
                "UPDATE orders_ordernumbersequence SET last_number = %s WHERE id = %s",
                [next_number, sequence_id],
            )
        conn.commit()
        return next_number
    finally:
        conn.close()


def test_order_number_sequence_under_two_concurrent_checkouts_never_collides():
    migrator_params = connections["migrator"].get_connection_params()
    user_params = connections["default"].get_connection_params()

    store_id, sequence_id = str(uuid7()), str(uuid7())

    setup_conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        _insert_store(setup_conn, store_id, f"seq-race-{store_id[:8]}")
        setup_conn.execute(
            "INSERT INTO orders_ordernumbersequence "
            "(id, created_at, updated_at, last_number, store_id) "
            "VALUES (%s, now(), now(), 0, %s)",
            [sequence_id, store_id],
        )

        numbers: list[int] = []
        errors: list[BaseException] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait()
            try:
                numbers.append(_allocate_order_number(user_params, sequence_id, store_id))
            except BaseException as exc:  # noqa: BLE001 -- must not leak past the thread either way
                errors.append(exc)

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []  # no IntegrityError (or anything else) leaked out
        assert sorted(numbers) == [1, 2]  # both succeeded, no lost increment, no duplicate

        with setup_conn.cursor() as cur:
            cur.execute(
                "SELECT last_number FROM orders_ordernumbersequence WHERE id = %s", [sequence_id]
            )
            (final_number,) = cur.fetchone()
        assert final_number == 2  # the sequence itself ends at the correct value
    finally:
        setup_conn.execute("DELETE FROM orders_ordernumbersequence WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM stores_store WHERE id = %s", [store_id])
        setup_conn.close()


# --------------------------------------------------------------------------
# 5. Single-order-per-CheckoutSession -- two concurrent `complete` attempts
#    on the SAME session with DIFFERENT Idempotency-Keys (review-round
#    finding: invariant #2 above only rules out reusing the SAME key; this
#    is the one that actually proves a session can't yield two Orders).
#    Exact lock sequence `apps.orders.services.checkout_complete` now runs
#    on `CheckoutSession` after the idempotency claim: `SELECT status ...
#    FOR UPDATE`, check `active`, flip to `completed`.
# --------------------------------------------------------------------------


def _try_complete_session(user_params, session_id: str, store_id: str) -> str:
    conn = psycopg.connect(**user_params, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_store_id', %s, true)", [store_id])
            cur.execute(
                "SELECT status FROM orders_checkoutsession WHERE id = %s FOR UPDATE", [session_id]
            )
            row = cur.fetchone()
            assert row is not None
            (status,) = row
            if status != "active":
                conn.rollback()
                return "rejected"
            cur.execute(
                "UPDATE orders_checkoutsession SET status = 'completed' WHERE id = %s",
                [session_id],
            )
        conn.commit()
        return "completed"  # stands in for "an Order was built and committed here"
    finally:
        conn.close()


def test_two_concurrent_completes_on_the_same_session_only_one_ever_builds_an_order():
    migrator_params = connections["migrator"].get_connection_params()
    user_params = connections["default"].get_connection_params()

    store_id, cart_id, session_id = str(uuid7()), str(uuid7()), str(uuid7())

    setup_conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        _insert_store(setup_conn, store_id, f"session-race-{store_id[:8]}")
        setup_conn.execute(
            "INSERT INTO carts_cart (id, created_at, updated_at, token_hash, status, currency, "
            "subtotal_amount, discount_amount, tax_amount, total_amount, store_id) "
            "VALUES (%s, now(), now(), %s, 'active', 'SAR', 0, 0, 0, 0, %s)",
            [cart_id, f"hash-{cart_id}", store_id],
        )
        setup_conn.execute(
            "INSERT INTO orders_checkoutsession "
            "(id, created_at, updated_at, status, expires_at, email, shipping_address, "
            "shipping_method_name_snapshot, cart_id, store_id) "
            "VALUES (%s, now(), now(), 'active', "
            "now() + interval '30 minutes', 'a@example.com', NULL, '', %s, %s)",
            [session_id, cart_id, store_id],
        )

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait()
            results.append(_try_complete_session(user_params, session_id, store_id))

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(results) == ["completed", "rejected"], results

        with setup_conn.cursor() as cur:
            cur.execute("SELECT status FROM orders_checkoutsession WHERE id = %s", [session_id])
            (final_status,) = cur.fetchone()
        assert final_status == "completed"  # exactly one transition ever happened
    finally:
        setup_conn.execute("DELETE FROM orders_checkoutsession WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM carts_cart WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM stores_store WHERE id = %s", [store_id])
        setup_conn.close()
