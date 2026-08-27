"""
Phase E ("product vision reset" -- Subscription Checkout). Merchant ->
platform billing ONLY -- strictly separate from `apps.payments`
(storefront customer -> merchant money, approved architecture decision
13, restated explicitly for this phase). This module never imports
`apps.payments`, never touches its models, and the reverse is also true.

Real sandbox provider, not a fake screen: `SubscriptionPaymentIntent`
genuinely transitions pending -> processing -> succeeded/failed/
cancelled as real, persisted, timestamped row updates, applied through
the SAME idempotent event-processing function (`apply_payment_event`)
whether the caller is the real HTTP webhook endpoint
(`apps.subscriptions.views.SubscriptionBillingWebhookView`) or this
module's own Celery task simulating the provider's callback --
mirroring `apps.payments.services.process_webhook` +
`apply_payment_transition`'s exact shape (explicit `_ALLOWED_TRANSITIONS`
adjacency, `WebhookEvent`-style create-or-IntegrityError delivery
dedup, `select_for_update` before every state read/write). There is no
`SUBSCRIPTION_BILLING_MODE=live` implementation here -- see
config/settings/base.py's two-gate comment; this file is reached at all
only when that setting reads exactly "demo".

Demo outcome selection uses a Stripe-test-card-style convention (a real,
widely-recognized sandbox pattern, not an invented one): a card number
ending "0002" declines, anything else succeeds. This is genuinely
testable locally and in CI with zero external network calls or
credentials -- exactly what "Sandbox Provider حقيقي قابل للاختبار
محليًا" asked for.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import IntegrityError, transaction

from apps.accounts.models import PlatformUser
from apps.subscriptions.models import (
    SubscriptionCheckoutSession,
    SubscriptionPaymentIntent,
    SubscriptionWebhookEvent,
)

# -- FSM: explicit adjacency, same discipline as apps.payments.services -----------
_TERMINAL_INTENT_STATES = frozenset(
    {
        SubscriptionPaymentIntent.State.SUCCEEDED,
        SubscriptionPaymentIntent.State.FAILED,
        SubscriptionPaymentIntent.State.CANCELLED,
    }
)
_ALLOWED_INTENT_TRANSITIONS: dict[str, frozenset[str]] = {
    SubscriptionPaymentIntent.State.PENDING: frozenset(
        {SubscriptionPaymentIntent.State.PROCESSING}
    ),
    SubscriptionPaymentIntent.State.PROCESSING: frozenset(
        {
            SubscriptionPaymentIntent.State.SUCCEEDED,
            SubscriptionPaymentIntent.State.FAILED,
            SubscriptionPaymentIntent.State.CANCELLED,
        }
    ),
    SubscriptionPaymentIntent.State.SUCCEEDED: frozenset(),
    SubscriptionPaymentIntent.State.FAILED: frozenset(),
    SubscriptionPaymentIntent.State.CANCELLED: frozenset(),
}

_EVENT_KIND_TO_STATE = {
    "payment.processing": SubscriptionPaymentIntent.State.PROCESSING,
    "payment.succeeded": SubscriptionPaymentIntent.State.SUCCEEDED,
    "payment.failed": SubscriptionPaymentIntent.State.FAILED,
    "payment.cancelled": SubscriptionPaymentIntent.State.CANCELLED,
}


class BillingModeError(Exception):
    """Raised the instant any billing entry point runs while
    `settings.SUBSCRIPTION_BILLING_MODE != "demo"`. Not an ordinary
    user-facing validation error -- it means subscription checkout is
    disabled outright in this environment (currently ALWAYS true outside
    local/test -- config/settings/production.py hardcodes "live", and no
    "live" provider integration exists yet)."""


class CheckoutNotPayableError(Exception):
    """Raised when there is no checkout session in a state payment can
    be initiated from (`ready_for_payment` for a first attempt,
    `payment_failed` for a retry -- see `_INITIATABLE_STATUSES`)."""


def require_demo_billing_mode() -> None:
    if settings.SUBSCRIPTION_BILLING_MODE != "demo":
        raise BillingModeError("Subscription checkout is not available in this environment.")


def simulate_demo_outcome(card_number: str) -> str:
    """Stripe-test-card convention: a number ending "0002" declines
    (Stripe's own real published test-decline number is
    4000000000000002), anything else succeeds. Never used for anything
    beyond picking which webhook event this module's own Celery task
    fires -- no card data is ever stored (`SubscriptionPaymentIntent`
    has no card-number field at all)."""
    digits = "".join(ch for ch in card_number if ch.isdigit())
    return "failed" if digits.endswith("0002") else "succeeded"


_INITIATABLE_STATUSES = (
    SubscriptionCheckoutSession.CheckoutStatus.READY_FOR_PAYMENT,
    SubscriptionCheckoutSession.CheckoutStatus.PAYMENT_FAILED,
)


def initiate_payment(*, user: PlatformUser, card_number: str) -> SubscriptionPaymentIntent:
    """Starts (or retries) a payment attempt on the user's own checkout
    session. `amount`/`currency` are read from `session.plan_version`
    ONLY -- `card_number` is never persisted and never used for
    anything except `simulate_demo_outcome` below; there is no field on
    this request the client could use to influence price. A retry after
    `payment_failed` creates a brand-new `SubscriptionPaymentIntent`
    (the failed one stays exactly as it resolved, for the audit trail)
    on the SAME `SubscriptionCheckoutSession` row -- never a second
    session (docs/PHASE_D... `uniq_active_checkout_session_per_user`
    already enforces this at the DB level too)."""
    require_demo_billing_mode()

    with transaction.atomic():
        # `select_related("plan_version")` deliberately NOT combined
        # with `select_for_update()` here -- real bug hit writing this:
        # `plan_version` is a nullable FK, and Postgres refuses
        # `SELECT ... FOR UPDATE` across a LEFT OUTER JOIN to the
        # nullable side ("FOR UPDATE cannot be applied to the nullable
        # side of an outer join"). Lock the session row alone; Django
        # transparently issues a second SELECT for `plan_version` the
        # first time it's accessed below (no select_for_update needed
        # on PlanVersion itself -- it's immutable platform data, never
        # written by app_user at all).
        session = (
            SubscriptionCheckoutSession.objects.select_for_update()
            .filter(user=user, checkout_status__in=_INITIATABLE_STATUSES)
            .first()
        )
        if session is None or session.plan_version is None:
            raise CheckoutNotPayableError(
                "No checkout session ready for payment -- select a plan first."
            )

        intent = SubscriptionPaymentIntent.objects.create(
            checkout_session=session,
            amount=session.plan_version.price_monthly,
            currency=session.plan_version.currency,
        )
        session.checkout_status = SubscriptionCheckoutSession.CheckoutStatus.PAYMENT_PENDING
        session.payment_status = SubscriptionCheckoutSession.PaymentStatus.PENDING
        session.save(update_fields=["checkout_status", "payment_status", "updated_at"])

    # Real bug found live-testing this phase (not caught by any pytest
    # run, for the exact reason explained below): dispatch the task
    # only via `transaction.on_commit`, never with a direct `.delay()`
    # here. This whole function runs inside `apps.stores.middleware.
    # TenantMiddleware`'s OWN request-spanning `transaction.atomic()`
    # (see config/settings/base.py's ATOMIC_REQUESTS note) -- so the
    # `with transaction.atomic():` block above is a NESTED savepoint,
    # not the real commit boundary. A `.delay()` called right after it
    # exits is still inside the outer, still-open, still-uncommitted
    # request transaction; a genuinely separate Celery worker process
    # queries the intent through its OWN connection and, under normal
    # Postgres MVCC, simply cannot see a row nothing has committed yet
    # -- `SubscriptionPaymentIntent.DoesNotExist`, observed for real
    # running a live worker against this exact code before this fix.
    # `CELERY_TASK_ALWAYS_EAGER` in tests hid this completely: eager
    # mode runs the task in-process, inside the SAME still-open
    # transaction, so it trivially sees its own uncommitted write --
    # this is `apps.core.events.emit_domain_event`'s exact, already-
    # proven pattern (see that function's own `transaction.on_commit`
    # call) for the identical reason, applied here.  Tests now use
    # `TestCase.captureOnCommitCallbacks(execute=True)` around the HTTP
    # call, Django's own sanctioned tool for firing on_commit hooks
    # without a real commit -- see test_subscription_checkout_billing.py.
    #
    # A consequence worth being explicit about: `intent` is genuinely
    # still "pending" at this point in EVERY environment now (not just
    # a real async one) -- the task has not run yet, only been
    # scheduled to run once this request's transaction actually
    # commits. Callers must not expect a resolved state back from this
    # call; that's what polling (GET .../payment-intent,
    # .../checkout-sessions/current) is for.
    outcome = simulate_demo_outcome(card_number)

    def _dispatch(intent_id: str = str(intent.id), outcome: str = outcome) -> None:
        # Import kept local to avoid a module-level Celery/task import
        # cycle with apps.subscriptions.tasks; default args capture the
        # values NOW, not whatever they are when the transaction
        # actually commits later.
        from apps.subscriptions.tasks import simulate_demo_payment_provider

        simulate_demo_payment_provider.delay(intent_id, outcome)

    transaction.on_commit(_dispatch)
    return intent


def get_active_intent(*, user: PlatformUser) -> SubscriptionPaymentIntent | None:
    """The current user's most recent payment intent, if any -- used by
    the checkout page to render pending/succeeded/failed state and by
    polling after `initiate_payment`. Scoped by `user` through the
    checkout session (never a client-held intent id), same "server is
    the only source of truth for identity" posture as
    `apps.subscriptions.services.get_active_checkout_session`."""
    return (
        SubscriptionPaymentIntent.objects.filter(checkout_session__user=user)
        .order_by("-created_at")
        .first()
    )


def apply_payment_event(
    *, intent_id: str | uuid.UUID, external_id: str, kind: str
) -> SubscriptionPaymentIntent:
    """The ONE place a `SubscriptionPaymentIntent`/its
    `SubscriptionCheckoutSession` actually change state in response to
    a provider event -- called identically by the real HTTP webhook
    view and by `apps.subscriptions.tasks.simulate_demo_payment_provider`
    (which just constructs a synthetic `external_id`/`kind` the same way
    a real provider's callback would arrive as). Idempotent on
    `external_id` exactly like `apps.payments.services.process_webhook`:
    a duplicate delivery increments `attempts` and returns without
    touching the intent a second time. Also safe against OUT-OF-ORDER
    delivery and a webhook arriving after the intent is already terminal
    -- `_ALLOWED_INTENT_TRANSITIONS`/`_TERMINAL_INTENT_STATES` make both
    a guaranteed no-op, not an error and not a silent re-application."""
    with transaction.atomic():
        try:
            with transaction.atomic():
                event = SubscriptionWebhookEvent.objects.create(
                    intent_id=intent_id, external_id=external_id, kind=kind
                )
        except IntegrityError:
            existing = SubscriptionWebhookEvent.objects.select_for_update().get(
                external_id=external_id
            )
            existing.attempts += 1
            existing.save(update_fields=["attempts", "updated_at"])
            return SubscriptionPaymentIntent.objects.get(id=intent_id)

        intent = SubscriptionPaymentIntent.objects.select_for_update().get(id=intent_id)

        if intent.state in _TERMINAL_INTENT_STATES:
            # Already resolved -- side effects already applied exactly
            # once. Duplicate/out-of-order/late delivery, all handled
            # the same way: record it (WebhookEvent above), touch
            # nothing else.
            event.processed_at = _now()
            event.save(update_fields=["processed_at", "updated_at"])
            return intent

        target_state = _EVENT_KIND_TO_STATE.get(kind)
        if target_state is None or target_state not in _ALLOWED_INTENT_TRANSITIONS.get(
            intent.state, frozenset()
        ):
            # An event type we don't act on, or one that doesn't apply
            # from the CURRENT state (e.g. "succeeded" arriving twice,
            # or arriving before "processing") -- recorded, not applied,
            # not an error.
            event.processed_at = _now()
            event.save(update_fields=["processed_at", "updated_at"])
            return intent

        intent.state = target_state
        if target_state == SubscriptionPaymentIntent.State.FAILED:
            intent.failure_reason = "card_declined"
        elif target_state == SubscriptionPaymentIntent.State.CANCELLED:
            intent.failure_reason = "cancelled"
        intent.save(update_fields=["state", "failure_reason", "updated_at"])

        if target_state in (
            SubscriptionPaymentIntent.State.SUCCEEDED,
            SubscriptionPaymentIntent.State.FAILED,
            SubscriptionPaymentIntent.State.CANCELLED,
        ):
            session = SubscriptionCheckoutSession.objects.select_for_update().get(
                id=intent.checkout_session_id
            )
            # Only act if the session is still waiting on THIS intent --
            # if it already moved on (shouldn't be possible given the
            # active-intent uniqueness constraint, but never trust a
            # webhook's timing over the session's own current state),
            # this is a no-op, not a forced overwrite.
            if (
                session.checkout_status
                == SubscriptionCheckoutSession.CheckoutStatus.PAYMENT_PENDING
            ):
                if target_state == SubscriptionPaymentIntent.State.SUCCEEDED:
                    session.checkout_status = (
                        SubscriptionCheckoutSession.CheckoutStatus.AWAITING_BUSINESS_INFO
                    )
                    session.payment_status = SubscriptionCheckoutSession.PaymentStatus.PAID
                else:
                    session.checkout_status = (
                        SubscriptionCheckoutSession.CheckoutStatus.PAYMENT_FAILED
                    )
                    session.payment_status = SubscriptionCheckoutSession.PaymentStatus.FAILED
                session.save(update_fields=["checkout_status", "payment_status", "updated_at"])

        event.processed_at = _now()
        event.save(update_fields=["processed_at", "updated_at"])
        return intent


def _now():
    from django.utils import timezone

    return timezone.now()
