"""
Domain-event consumption for Phase 11. `process_committed_event` is the
ONE place that turns a committed `order.confirmed` `EventLog` row into
an actually-sent email -- called from both the fast-path Celery task and
the recovery sweep (apps/notifications/tasks.py), so there is exactly
one implementation of "how to process this event", not two.

Explicit non-goal (approved review-round scope): a notification-delivery
failure must NEVER surface into Order/Payment/Inventory correctness --
this module only ever mutates its own `NotificationDispatch` rows, never
calls back into `apps.orders`/`apps.payments` write paths.
"""

from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.models import EventLog
from apps.notifications.channels.base import PermanentSendError
from apps.notifications.channels.email import EmailChannel
from apps.notifications.models import NotificationDispatch, NotificationTemplate
from apps.notifications.rendering import build_order_confirmation_context, render_template

# Authoritative retry ceiling -- tracked on `NotificationDispatch.attempts`,
# not solely by Celery's own retry count (see apps/notifications/tasks.py's
# docstring on why the two are not perfectly synchronized, and why that's
# an accepted, documented limitation rather than a correctness gap: the
# recovery sweep re-invokes this same idempotent function regardless of
# how Celery's own retry chain ended).
_MAX_ATTEMPTS = 5


class TemplateNotConfiguredError(Exception):
    """No active NotificationTemplate exists for this key, in either the
    resolved locale or the platform default -- a configuration gap, not
    a transient failure. Never retried automatically."""


def resolve_locale(store) -> str:
    """Phase 11 has no real per-store or per-customer language preference
    yet (approved review-round scope: do not invent a customer-preference
    model just for this). `getattr(..., None)` makes this forward-
    compatible with a future `Store.default_language` field with zero
    changes here -- today nothing sets it, so every store resolves to the
    platform default (`settings.LANGUAGE_CODE`)."""
    return getattr(store, "default_language", None) or settings.LANGUAGE_CODE


def _get_template(*, key: str, locale: str) -> NotificationTemplate:
    template = NotificationTemplate.objects.filter(key=key, locale=locale, is_active=True).first()
    if template is None and locale != settings.LANGUAGE_CODE:
        template = NotificationTemplate.objects.filter(
            key=key, locale=settings.LANGUAGE_CODE, is_active=True
        ).first()
    if template is None:
        raise TemplateNotConfiguredError(
            f"No active NotificationTemplate for key={key!r} "
            f"(locale={locale!r} or platform default {settings.LANGUAGE_CODE!r})."
        )
    return template


def _mark_terminal(dispatch_id, *, status: str, error: Exception) -> None:
    with transaction.atomic(using="default"):
        NotificationDispatch.objects.filter(id=dispatch_id).update(
            status=status, last_error=str(error)[:2000], updated_at=timezone.now()
        )


def _record_transient_failure(dispatch_id, *, error: Exception) -> bool:
    """Returns True if this failure just pushed the dispatch into the
    terminal DEAD_LETTER state (caller must stop retrying), False if
    it's still retryable."""
    with transaction.atomic(using="default"):
        dispatch = NotificationDispatch.objects.select_for_update().get(id=dispatch_id)
        dispatch.attempts += 1
        dispatch.last_error = str(error)[:2000]
        went_terminal = dispatch.attempts >= _MAX_ATTEMPTS
        if went_terminal:
            dispatch.status = NotificationDispatch.Status.DEAD_LETTER
        dispatch.save(update_fields=["attempts", "last_error", "status", "updated_at"])
    return went_terminal


def process_committed_event(*, event: EventLog) -> None:
    """
    Must be called with tenant context already set to `event.store_id`
    (apps/notifications/tasks.py does this). Splits into short
    transactions around the network send -- never holds a PostgreSQL
    lock/open transaction during SMTP/network I/O, same discipline as
    `apps.payments.services.initiate_payment`.

    Idempotent by construction: claims (or fetches) exactly one
    `NotificationDispatch` row for `(store, event, channel,
    notification_type)` and no-ops immediately if it's already in a
    terminal state -- safe to call repeatedly for the same event (a
    Celery retry, the recovery sweep, or both racing).

    Raises the underlying exception ONLY when the failure is still
    retryable (so the Celery task's own retry/backoff applies); returns
    normally for every other outcome (sent, permanently failed, or just
    dead-lettered) -- those are terminal and recorded on the
    `NotificationDispatch` row itself, nothing for the caller to react to.
    """
    from apps.orders.models import Order  # local: notifications sits above

    # orders in the approved layering (an allowed import), kept local
    # only so it reads next to its one call site below.

    if event.event_type != "order.confirmed":
        return
    order_id = event.payload.get("aggregate_id")
    if not order_id:
        return

    with transaction.atomic(using="default"):
        try:
            order = Order.objects.select_related("store").get(id=order_id)
        except Order.DoesNotExist:
            return
        dispatch, _created = NotificationDispatch.objects.get_or_create(
            store=order.store,
            event=event,
            channel=NotificationDispatch.Channel.EMAIL,
            notification_type="order_confirmation",
            defaults={"recipient": order.email, "status": NotificationDispatch.Status.PENDING},
        )
        if dispatch.status != NotificationDispatch.Status.PENDING:
            return  # already terminal (SENT/FAILED/DEAD_LETTER) -- idempotent no-op

    try:
        locale = resolve_locale(order.store)
        template = _get_template(key=dispatch.notification_type, locale=locale)
        context = build_order_confirmation_context(order=order, store=order.store)
        subject, body = render_template(template=template, context=context)
        EmailChannel().send(recipient=dispatch.recipient, subject=subject, body=body)
    except (PermanentSendError, TemplateNotConfiguredError) as exc:
        _mark_terminal(dispatch.id, status=NotificationDispatch.Status.FAILED, error=exc)
        return
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: any other
        # exception (SMTP timeout, connection refused, ...) is treated as
        # transient and retried, up to _MAX_ATTEMPTS.
        went_terminal = _record_transient_failure(dispatch.id, error=exc)
        if went_terminal:
            return
        raise

    with transaction.atomic(using="default"):
        NotificationDispatch.objects.filter(id=dispatch.id).update(
            status=NotificationDispatch.Status.SENT,
            sent_at=timezone.now(),
            updated_at=timezone.now(),
        )
