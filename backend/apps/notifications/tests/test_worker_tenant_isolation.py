"""
Phase 11 review round 2, required regression: a real Celery worker
process has no HTTP request, no inherited GUC, nothing left over from
whoever published the task -- `process_domain_event` must derive its
tenant context entirely from the durable `EventLog.store_id`, never from
anything ambient. `CELERY_TASK_ALWAYS_EAGER` (test/dev) executes the task
inline on the calling thread, which could silently mask a worker that
actually depends on inherited context -- this test proves the opposite
by making certain NO tenant context (neither the Python `ContextVar` nor
the PostgreSQL session GUC) is active anywhere before the task runs, then
invoking the exact same path a real worker uses: `config.celery.app`'s
own task registry + `apply_async`, the identical call
`apps.core.events.emit_domain_event` makes -- not a bare Python function
call to the task body.
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.db import connection

from apps.core.models import EventLog
from apps.notifications.models import NotificationDispatch
from apps.notifications.tests.conftest import (
    add_item_and_start_checkout,
    add_stock,
    complete_address_and_shipping,
    setup_flat_shipping,
)
from apps.orders.models import Order
from apps.orders.services import confirm_order
from apps.orders.tests.conftest import store_db_context
from apps.tenancy.context import get_current_store_id
from config.celery import app as celery_app

pytestmark = pytest.mark.django_db


def _raw_db_guc() -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting(%s, true)", ["app.current_store_id"])
        (value,) = cursor.fetchone()
    return value or ""


def test_worker_derives_tenant_context_from_the_event_with_no_inherited_state(
    variant_in_store, storefront_client
):
    ctx = variant_in_store
    mail.outbox.clear()

    # Build Store A / Order A / a committed order.confirmed EventLog with
    # NO dispatch yet -- `confirm_order` called directly, bypassing
    # `emit_domain_event`'s on_commit hook entirely (same shape as
    # test_recovery.py's `_pending_confirmed_order_with_no_dispatch`),
    # so nothing has touched the notification worker path yet.
    add_stock(ctx["store"], ctx["variant_id"])
    add_item_and_start_checkout(storefront_client, ctx["variant_id"])
    method = setup_flat_shipping(ctx)
    complete_address_and_shipping(storefront_client, method["id"])
    response = storefront_client.post(
        "/api/v1/storefront/checkout/complete",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="worker-isolation-1",
    )
    assert response.status_code == 201, response.data
    order_data = response.data

    with store_db_context(ctx["store"]):
        from django.db import transaction

        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_data["id"])
            confirm_order(order=order)  # writes EventLog; on_commit never captured/run
    # `store_db_context` clears both the Python ContextVar and the DB GUC
    # on exit -- explicitly re-verified below rather than trusted blindly.

    with store_db_context(ctx["store"]):
        event = EventLog.objects.filter(
            event_type="order.confirmed", payload__aggregate_id=order_data["id"]
        ).get()

    # Prove NO tenant context is active anywhere -- neither layer --
    # before invoking the worker path. This is the actual regression
    # guard: without it, a worker bug that silently relies on inherited
    # context could pass by accident under CELERY_TASK_ALWAYS_EAGER.
    assert get_current_store_id() is None
    assert _raw_db_guc() == ""

    # Invoke the exact path a real Celery worker uses: the task looked up
    # by name from the app's own registry, `apply_async` -- the same call
    # `apps.core.events.emit_domain_event` makes, NOT a bare Python
    # function call to the task body.
    result = celery_app.tasks["apps.notifications.tasks.process_domain_event"].apply_async(
        kwargs={"event_id": str(event.id)}
    )
    result.get(timeout=5)

    # Still no leaked context afterward -- the task cleaned up its own.
    assert get_current_store_id() is None
    assert _raw_db_guc() == ""

    with store_db_context(ctx["store"]):
        dispatch = NotificationDispatch.objects.get(
            event=event, notification_type="order_confirmation"
        )
    assert dispatch.store_id == ctx["store"].id
    assert dispatch.status == NotificationDispatch.Status.SENT
    assert dispatch.recipient == order_data["email"]
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [order_data["email"]]
    assert order_data["number"] in mail.outbox[0].subject
