"""
Phase 15 -- MVP analytics, derived live from PostgreSQL via ordinary
Django ORM aggregation. Deliberately NOT a rollup/read-model table fed by
a Celery Beat task (an earlier, more elaborate design sketch in
docs/ARCHITECTURE.md's directory layout) -- the approved Phase 15
instruction is "avoid building a data warehouse or event pipeline
prematurely; derive MVP analytics from PostgreSQL where practical". A
live `aggregate()`/`annotate()` query trivially satisfies the DoD
("numbers match the source", since it query the source directly), costs
nothing to add later on top of (a rollup/cache layer can be introduced
without changing this module's public function signatures if traffic
ever demands it), and needs zero new tables/migrations for an MVP scale.

Store-scoped functions here run under the caller's ALREADY-ESTABLISHED
tenant context (ordinary `Order.objects`, standard RLS via the "default"
connection) -- no privileged DB access of any kind. This app owns ONLY
the merchant-facing, per-store surface; the platform-wide equivalent
lives in apps.platform_admin.services (extends its existing
overview_metrics()), reusing the Phase 14-approved privileged boundary
instead of opening a second cross-tenant code path here.

Revenue counts CONFIRMED orders only (apps.orders.models.Order.Status.CONFIRMED,
set only once payment has actually succeeded -- apps.orders.services.confirm_order)
-- never duplicates apps.payments' own ledger, just reads the Order
model's own total_amount snapshot, the same number the merchant/customer
already sees on the order itself.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.orders.models import Order
from apps.stores.models import Store

_TIME_SERIES_DAYS = 30


def store_overview_metrics(*, store: Store) -> dict[str, Any]:
    orders = Order.objects.filter(store=store)

    orders_by_status = dict(orders.values_list("status").annotate(count=Count("id")).order_by())

    revenue_by_currency = dict(
        orders.filter(status=Order.Status.CONFIRMED)
        .values_list("currency")
        .annotate(total=Sum("total_amount"))
        .order_by()
    )

    since = timezone.now() - timedelta(days=_TIME_SERIES_DAYS)
    daily_counts = (
        orders.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    return {
        "orders_total": orders.count(),
        "orders_by_status": orders_by_status,
        "revenue_by_currency": revenue_by_currency,
        "orders_last_30_days": [
            {"date": row["day"].isoformat(), "count": row["count"]} for row in daily_counts
        ],
    }
