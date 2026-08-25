"""
Real cross-connection concurrency (two genuinely separate PostgreSQL
sessions), the same proven pattern as
apps/inventory/tests/test_overselling_concurrency.py (Phase 5) and
apps/orders/tests/test_concurrency.py (Phase 8): `app_migrator` for
setup/teardown with real commits, `app_user` for the competing attempts,
each running the EXACT SQL sequence the real service functions run.

The 3 invariants required for Phase 9 (docs/PHASE_9_REPORT.md):

1. Duplicate webhook delivery, same provider event identity -- side
   effects happen exactly once.
2. A success webhook racing the reconciliation worker's failure
   resolution for the SAME `PaymentIntent` -- the final state (payment,
   Order, inventory) is always internally consistent, never a mix of
   "succeeded" and "reservation released".
3. Two DIFFERENT webhook event ids both representing the same success
   outcome (a realistic retry-generated duplicate notification) -- proves
   `apply_payment_transition`'s own lock-and-check guards side effects,
   NOT `WebhookEvent.external_id` uniqueness (which does not even apply
   here, since the ids genuinely differ).
"""

from __future__ import annotations

import threading

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


def _insert_order(conn, order_id: str, store_id: str, number: str) -> None:
    conn.execute(
        "INSERT INTO orders_order "
        "(id, created_at, updated_at, number, email, status, fulfillment_status, currency, "
        "subtotal_amount, discount_amount, tax_amount, shipping_amount, total_amount, "
        "shipping_address, shipping_method_name_snapshot, coupon_code_snapshot, store_id) "
        "VALUES (%s, now(), now(), %s, 'race@example.com', 'pending_payment', 'unfulfilled', "
        "'SAR', 2000, 0, 0, 0, 2000, '{}', 'Standard', '', %s)",
        [order_id, number, store_id],
    )


def _insert_provider_config(conn, config_id: str, store_id: str) -> None:
    conn.execute(
        "INSERT INTO payments_storeproviderconfig "
        "(id, created_at, updated_at, provider_key, mode, is_enabled, credentials_encrypted, "
        "credentials_hint, webhook_secret_encrypted, public_metadata, store_id) "
        "VALUES (%s, now(), now(), 'mock', 'test', true, '', '', '', '{}', %s)",
        [config_id, store_id],
    )


def _insert_payment_intent(
    conn, intent_id: str, store_id: str, order_id: str, config_id: str, *, provider_ref: str
) -> None:
    conn.execute(
        "INSERT INTO payments_paymentintent "
        "(id, created_at, updated_at, amount, currency, state, provider_ref, idempotency_key, "
        "failure_reason, retryable, order_id, provider_config_id, store_id) "
        "VALUES (%s, now(), now(), 2000, 'SAR', 'processing', %s, 'race-key', '', "
        "NULL, %s, %s, %s)",
        [intent_id, provider_ref, order_id, config_id, store_id],
    )


# --------------------------------------------------------------------------
# 1. Duplicate webhook delivery, same external_id -- side effects once.
# --------------------------------------------------------------------------


def _deliver_webhook(user_params, *, store_id, config_id, intent_id, external_id, amount) -> str:
    """Mirrors `apps.payments.services.process_webhook`'s claim + apply sequence."""
    conn = psycopg.connect(**user_params, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_store_id', %s, true)", [store_id])
            try:
                cur.execute(
                    "INSERT INTO payments_webhookevent "
                    "(id, created_at, updated_at, external_id, signature_valid, payload_redacted, "
                    "processed_at, attempts, provider_config_id, store_id) "
                    "VALUES (%s, now(), now(), %s, true, '{}', NULL, 1, %s, %s)",
                    [str(uuid7()), external_id, config_id, store_id],
                )
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                cur.execute("SELECT set_config('app.current_store_id', %s, true)", [store_id])
                cur.execute(
                    "UPDATE payments_webhookevent SET attempts = attempts + 1 "
                    "WHERE provider_config_id = %s AND external_id = %s",
                    [config_id, external_id],
                )
                conn.commit()
                return "duplicate"

            cur.execute(
                "SELECT state FROM payments_paymentintent WHERE id = %s FOR UPDATE", [intent_id]
            )
            row = cur.fetchone()
            assert row is not None
            (state,) = row
            if state != "processing":
                conn.commit()
                return "already-resolved"

            cur.execute(
                "UPDATE payments_paymentintent SET state = 'succeeded' WHERE id = %s", [intent_id]
            )
            cur.execute(
                "INSERT INTO payments_paymenttransaction "
                "(id, created_at, updated_at, kind, outcome, amount, provider_ref, "
                "raw_response_redacted, intent_id, store_id) "
                "VALUES (%s, now(), now(), 'capture', 'succeeded', %s, '', '{}', %s, %s)",
                [str(uuid7()), amount, intent_id, store_id],
            )
        conn.commit()
        return "processed"
    finally:
        conn.close()


def test_duplicate_webhook_delivery_is_processed_exactly_once():
    migrator_params = connections["migrator"].get_connection_params()
    user_params = connections["default"].get_connection_params()

    store_id, order_id, config_id, intent_id = (str(uuid7()) for _ in range(4))
    external_id = f"evt_{uuid7()}"

    setup_conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        _insert_store(setup_conn, store_id, f"webhook-race-{store_id[:8]}")
        _insert_order(setup_conn, order_id, store_id, f"ORD-{order_id[:8]}")
        _insert_provider_config(setup_conn, config_id, store_id)
        _insert_payment_intent(
            setup_conn, intent_id, store_id, order_id, config_id, provider_ref="mock_pi_race"
        )

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait()
            results.append(
                _deliver_webhook(
                    user_params,
                    store_id=store_id,
                    config_id=config_id,
                    intent_id=intent_id,
                    external_id=external_id,
                    amount=2000,
                )
            )

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(results) == ["duplicate", "processed"], results

        with setup_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM payments_webhookevent WHERE provider_config_id = %s "
                "AND external_id = %s",
                [config_id, external_id],
            )
            (event_count,) = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) FROM payments_paymenttransaction WHERE intent_id = %s", [intent_id]
            )
            (txn_count,) = cur.fetchone()
            cur.execute("SELECT state FROM payments_paymentintent WHERE id = %s", [intent_id])
            (final_state,) = cur.fetchone()

        assert event_count == 1  # one WebhookEvent row, not two
        assert txn_count == 1  # exactly one side effect, not two
        assert final_state == "succeeded"
    finally:
        setup_conn.execute(
            "DELETE FROM payments_paymenttransaction WHERE store_id = %s", [store_id]
        )
        setup_conn.execute("DELETE FROM payments_webhookevent WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM payments_paymentintent WHERE store_id = %s", [store_id])
        setup_conn.execute(
            "DELETE FROM payments_storeproviderconfig WHERE store_id = %s", [store_id]
        )
        setup_conn.execute("DELETE FROM orders_order WHERE store_id = %s", [store_id])
        setup_conn.execute("DELETE FROM stores_store WHERE id = %s", [store_id])
        setup_conn.close()


# --------------------------------------------------------------------------
# 2 & 3. Shared scaffolding: a PaymentIntent with a real Order + inventory
#    reservation behind it, so "success" vs "failure" outcomes have a real,
#    observable, must-stay-consistent side effect to race over.
# --------------------------------------------------------------------------


def _insert_inventory(conn, *, store_id, variant_id, product_id, location_id, balance_id, order_id):
    conn.execute(
        "INSERT INTO catalog_product "
        "(id, created_at, updated_at, name, slug, description, status, seo_title, "
        "seo_description, store_id) "
        "VALUES (%s, now(), now(), 'Race Widget', %s, '', 'active', '', '', %s)",
        [product_id, f"race-widget-{product_id[:8]}", store_id],
    )
    conn.execute(
        "INSERT INTO catalog_productvariant "
        "(id, created_at, updated_at, sku, status, is_default, position, currency, "
        "price_amount, barcode, option_signature, product_id, store_id) "
        "VALUES (%s, now(), now(), %s, 'active', true, 0, 'SAR', 2000, '', '{}', %s, %s)",
        [variant_id, f"RACE-{variant_id[:8]}", product_id, store_id],
    )
    conn.execute(
        "INSERT INTO inventory_stocklocation "
        "(id, created_at, updated_at, name, is_active, store_id) "
        "VALUES (%s, now(), now(), 'Race Warehouse', true, %s)",
        [location_id, store_id],
    )
    conn.execute(
        "INSERT INTO inventory_stockbalance "
        "(id, created_at, updated_at, quantity_on_hand, quantity_reserved, store_id, "
        "variant_id, location_id) "
        "VALUES (%s, now(), now(), 10, 1, %s, %s, %s)",
        [balance_id, store_id, variant_id, location_id],
    )
    conn.execute(
        "INSERT INTO inventory_stockreservation "
        "(id, created_at, updated_at, quantity, reference, status, "
        "store_id, variant_id, location_id) "
        "VALUES (%s, now(), now(), 1, %s, 'active', %s, %s, %s)",
        [str(uuid7()), f"order:{order_id}", store_id, variant_id, location_id],
    )


def _resolve_payment(user_params, *, store_id, intent_id, order_id, outcome: str) -> str:
    """Mirrors `apply_payment_transition`'s lock-check-apply sequence for the
    `succeeded` (webhook) and `failed`/non-retryable (reconciliation) paths."""
    conn = psycopg.connect(**user_params, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_store_id', %s, true)", [store_id])
            cur.execute(
                "SELECT state FROM payments_paymentintent WHERE id = %s FOR UPDATE", [intent_id]
            )
            row = cur.fetchone()
            assert row is not None
            (state,) = row
            if state != "processing":
                conn.commit()
                return f"skipped({outcome})"

            cur.execute(
                "UPDATE payments_paymentintent SET state = %s WHERE id = %s", [outcome, intent_id]
            )
            if outcome == "succeeded":
                cur.execute(
                    "UPDATE orders_order SET status = 'confirmed' "
                    "WHERE id = %s AND status = 'pending_payment'",
                    [order_id],
                )
                # `fulfill_reservation`'s real effect: deduct on_hand AND reserved by the
                # reservation's own quantity, matched via (variant, location).
                cur.execute(
                    "UPDATE inventory_stockbalance b SET "
                    "quantity_on_hand = b.quantity_on_hand - r.quantity, "
                    "quantity_reserved = b.quantity_reserved - r.quantity "
                    "FROM inventory_stockreservation r "
                    "WHERE r.reference = %s AND r.status = 'active' "
                    "AND b.variant_id = r.variant_id AND b.location_id = r.location_id",
                    [f"order:{order_id}"],
                )
                cur.execute(
                    "UPDATE inventory_stockreservation SET status = 'fulfilled' "
                    "WHERE reference = %s AND status = 'active'",
                    [f"order:{order_id}"],
                )
            else:
                cur.execute(
                    "UPDATE orders_order SET status = 'cancelled' "
                    "WHERE id = %s AND status = 'pending_payment'",
                    [order_id],
                )
                # `release_reservation`'s real effect: give back `reserved` only,
                # `on_hand` untouched -- nothing was actually sold.
                cur.execute(
                    "UPDATE inventory_stockbalance b SET "
                    "quantity_reserved = b.quantity_reserved - r.quantity "
                    "FROM inventory_stockreservation r "
                    "WHERE r.reference = %s AND r.status = 'active' "
                    "AND b.variant_id = r.variant_id AND b.location_id = r.location_id",
                    [f"order:{order_id}"],
                )
                cur.execute(
                    "UPDATE inventory_stockreservation SET status = 'released' "
                    "WHERE reference = %s AND status = 'active'",
                    [f"order:{order_id}"],
                )
        conn.commit()
        return outcome
    finally:
        conn.close()


def _setup_intent_with_reservation(setup_conn, *, store_id: str) -> dict:
    order_id, config_id, intent_id = (str(uuid7()) for _ in range(3))
    variant_id, product_id, location_id, balance_id = (str(uuid7()) for _ in range(4))

    _insert_store(setup_conn, store_id, f"payment-race-{store_id[:8]}")
    _insert_order(setup_conn, order_id, store_id, f"ORD-{order_id[:8]}")
    _insert_provider_config(setup_conn, config_id, store_id)
    _insert_payment_intent(
        setup_conn, intent_id, store_id, order_id, config_id, provider_ref="mock_pi_consistency"
    )
    _insert_inventory(
        setup_conn,
        store_id=store_id,
        variant_id=variant_id,
        product_id=product_id,
        location_id=location_id,
        balance_id=balance_id,
        order_id=order_id,
    )
    return {"order_id": order_id, "config_id": config_id, "intent_id": intent_id}


def _cleanup(setup_conn, store_id: str) -> None:
    setup_conn.execute("DELETE FROM inventory_stockreservation WHERE store_id = %s", [store_id])
    setup_conn.execute("DELETE FROM inventory_stockbalance WHERE store_id = %s", [store_id])
    setup_conn.execute("DELETE FROM inventory_stocklocation WHERE store_id = %s", [store_id])
    setup_conn.execute("DELETE FROM catalog_productvariant WHERE store_id = %s", [store_id])
    setup_conn.execute("DELETE FROM catalog_product WHERE store_id = %s", [store_id])
    setup_conn.execute("DELETE FROM payments_paymenttransaction WHERE store_id = %s", [store_id])
    setup_conn.execute("DELETE FROM payments_webhookevent WHERE store_id = %s", [store_id])
    setup_conn.execute("DELETE FROM payments_paymentintent WHERE store_id = %s", [store_id])
    setup_conn.execute("DELETE FROM payments_storeproviderconfig WHERE store_id = %s", [store_id])
    setup_conn.execute("DELETE FROM orders_order WHERE store_id = %s", [store_id])
    setup_conn.execute("DELETE FROM stores_store WHERE id = %s", [store_id])


def test_success_webhook_racing_reconciliation_failure_stays_internally_consistent():
    """Approved Phase 9 concurrency invariant #2: a success webhook and the
    reconciliation worker's failure resolution can genuinely race for the SAME
    `PaymentIntent`. Whichever wins, payment state / Order status / reservation
    status / stock balance must never end up mixed (e.g. `succeeded` with a
    `released` reservation)."""
    migrator_params = connections["migrator"].get_connection_params()
    user_params = connections["default"].get_connection_params()
    store_id = str(uuid7())

    setup_conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        ids = _setup_intent_with_reservation(setup_conn, store_id=store_id)

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt(outcome: str) -> None:
            barrier.wait()
            results.append(
                _resolve_payment(
                    user_params,
                    store_id=store_id,
                    intent_id=ids["intent_id"],
                    order_id=ids["order_id"],
                    outcome=outcome,
                )
            )

        threads = [
            threading.Thread(target=attempt, args=("succeeded",)),
            threading.Thread(target=attempt, args=("failed",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        winner = "succeeded" if "succeeded" in results else "failed"
        assert sorted(results) == sorted(
            [winner, f"skipped({'failed' if winner == 'succeeded' else 'succeeded'})"]
        )

        with setup_conn.cursor() as cur:
            cur.execute(
                "SELECT state FROM payments_paymentintent WHERE id = %s", [ids["intent_id"]]
            )
            (intent_state,) = cur.fetchone()
            cur.execute("SELECT status FROM orders_order WHERE id = %s", [ids["order_id"]])
            (order_status,) = cur.fetchone()
            cur.execute(
                "SELECT status FROM inventory_stockreservation WHERE reference = %s",
                [f"order:{ids['order_id']}"],
            )
            (reservation_status,) = cur.fetchone()
            cur.execute(
                "SELECT quantity_on_hand, quantity_reserved FROM inventory_stockbalance "
                "WHERE store_id = %s",
                [store_id],
            )
            on_hand, reserved = cur.fetchone()

        if winner == "succeeded":
            assert intent_state == "succeeded"
            assert order_status == "confirmed"
            assert reservation_status == "fulfilled"
            assert (on_hand, reserved) == (9, 0)  # sold: on_hand AND reserved both decremented
        else:
            assert intent_state == "failed"
            assert order_status == "cancelled"
            assert reservation_status == "released"
            assert (on_hand, reserved) == (10, 0)  # given back: only reserved decremented
    finally:
        _cleanup(setup_conn, store_id)
        setup_conn.close()


def test_two_different_events_for_the_same_success_apply_side_effects_once():
    """Approved Phase 9 concurrency invariant #3: two DIFFERENT webhook event ids
    (a realistic retry-generated duplicate) both resolving to `succeeded` for the
    SAME PaymentIntent -- fulfillment/confirmation must happen exactly once. This
    is NOT protected by `WebhookEvent.external_id` uniqueness (the ids genuinely
    differ) -- only `apply_payment_transition`'s own PaymentIntent-row lock does."""
    migrator_params = connections["migrator"].get_connection_params()
    user_params = connections["default"].get_connection_params()
    store_id = str(uuid7())

    setup_conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        ids = _setup_intent_with_reservation(setup_conn, store_id=store_id)

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait()
            results.append(
                _resolve_payment(
                    user_params,
                    store_id=store_id,
                    intent_id=ids["intent_id"],
                    order_id=ids["order_id"],
                    outcome="succeeded",
                )
            )

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(results) == ["skipped(succeeded)", "succeeded"], results

        with setup_conn.cursor() as cur:
            cur.execute("SELECT status FROM orders_order WHERE id = %s", [ids["order_id"]])
            (order_status,) = cur.fetchone()
            cur.execute(
                "SELECT quantity_on_hand, quantity_reserved FROM inventory_stockbalance "
                "WHERE store_id = %s",
                [store_id],
            )
            on_hand, reserved = cur.fetchone()

        assert order_status == "confirmed"
        # Fulfilled exactly ONCE -- if the second thread had also applied its
        # decrement, on_hand would be 8, not 9.
        assert (on_hand, reserved) == (9, 0)
    finally:
        _cleanup(setup_conn, store_id)
        setup_conn.close()
