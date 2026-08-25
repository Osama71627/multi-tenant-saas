"""
Payment orchestration. Kept out of views per docs/ARCHITECTURE.md section
11, same as every prior app.

Three separate points of discipline run through this whole file (all
approved Phase 9 decisions):

1. Network calls to the provider NEVER happen inside an open
   `transaction.atomic()` -- `initiate_payment` deliberately splits into
   three short DB transactions around one un-transacted provider call.
2. The provider-side idempotency key passed to `create_payment` is
   derived from the CLIENT's own Idempotency-Key, not freshly generated
   -- so a retry (client-driven or our own crash-recovery) reaches the
   provider with the SAME key every time, closing the dual-write gap at
   the provider's own idempotency guarantee.
3. `apply_payment_transition` is THE one place that ever mutates
   `PaymentIntent.state` or cascades into `Order`/inventory -- webhook
   processing AND the reconciliation worker both call it, so there is
   exactly one implementation of "what happens when a payment resolves",
   not two. It re-fetches and locks the `PaymentIntent` row and checks
   its CURRENT state before doing anything, which is what makes it safe
   under real concurrency independent of `WebhookEvent` uniqueness
   (approved Phase 9 decision on the concurrency tests -- see
   apps/payments/tests/test_concurrency.py).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.orders import services as order_services
from apps.orders.models import Order
from apps.payments import encryption
from apps.payments.models import (
    PaymentIdempotencyKey,
    PaymentIntent,
    PaymentTransaction,
    StoreProviderConfig,
    WebhookEvent,
)
from apps.payments.providers.base import (
    PaymentContext,
    PaymentProvider,
    SignatureVerificationError,
)
from apps.payments.providers.registry import get_provider
from apps.stores.models import Store
from apps.subscriptions import entitlements

# -- FSM: explicit adjacency, not numeric ordering (approved Phase 9 decision) --------
_TERMINAL_STATES = frozenset(
    {PaymentIntent.State.SUCCEEDED, PaymentIntent.State.FAILED, PaymentIntent.State.CANCELLED}
)
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    PaymentIntent.State.PROCESSING: frozenset(
        {PaymentIntent.State.SUCCEEDED, PaymentIntent.State.FAILED, PaymentIntent.State.CANCELLED}
    ),
    PaymentIntent.State.SUCCEEDED: frozenset(),
    PaymentIntent.State.FAILED: frozenset(),
    PaymentIntent.State.CANCELLED: frozenset(),
}


class ProviderNotConfiguredError(Exception):
    pass


class OrderNotPayableError(Exception):
    """The Order isn't `pending_payment` -- nothing to pay for (already confirmed,
    already cancelled, or never existed in a payable state)."""


class DuplicateActivePaymentIntentError(Exception):
    """This Order already has a `processing` PaymentIntent -- resolve or wait for it
    before starting another (the DB partial-unique constraint is the real guard;
    this is the friendly, pre-checked error for the common case)."""


class IdempotencyKeyRequiredError(Exception):
    pass


class IdempotencyConflictError(Exception):
    """Same key reused for a materially different request, or a prior attempt with
    this exact key is still in flight (a genuinely reachable state here, unlike
    apps.orders.checkout_complete -- see this module's docstring, point 1)."""


class InvalidWebhookError(Exception):
    pass


class NotManualCodError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PaymentInitiateResult:
    response_status: int
    response_body: dict
    created: bool


def get_provider_for_config(config: StoreProviderConfig) -> PaymentProvider:
    # Empty default, not a credential -- filled in below only for the stripe provider.
    secret_key = ""  # nosec B105
    if config.provider_key == "stripe":
        secret_key = encryption.decrypt_secret(config.credentials_encrypted)
    return get_provider(provider_key=config.provider_key, secret_key=secret_key)


def _fingerprint(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()


def _intent_body(intent: PaymentIntent) -> dict:
    return {
        "id": str(intent.id),
        "order_id": str(intent.order_id),
        "state": intent.state,
        "amount": intent.amount,
        "currency": intent.currency,
        "provider_key": intent.provider_config.provider_key,
    }


def initiate_payment(
    *, order: Order, store: Store, provider_key: str, idempotency_key: str
) -> PaymentInitiateResult:
    """
    Phase 10, approved architecture decision 11: a `read_only` Store stops
    NEW purchase/payment attempts -- checked FIRST, before the idempotency
    claim or any other side effect, so a rejected call leaves nothing
    behind (no claimed key, no provider call). This is deliberately
    narrower than "block everything payment-related for this Store":
    `process_webhook`, `apply_payment_transition`, reconciliation, and
    `capture_manual_cod_payment` all complete or recover an ALREADY-
    STARTED PaymentIntent, not a new purchase attempt, and must keep
    working regardless of the Store's current status -- an in-flight
    payment must still be able to resolve.
    """
    entitlements.require_active_store(store=store)

    if not idempotency_key:
        raise IdempotencyKeyRequiredError("Idempotency-Key header is required.")

    try:
        config = StoreProviderConfig.objects.get(provider_key=provider_key, is_enabled=True)
    except StoreProviderConfig.DoesNotExist as exc:
        raise ProviderNotConfiguredError(
            f"No enabled provider configuration for {provider_key!r}."
        ) from exc

    fingerprint = _fingerprint(str(order.id), provider_key)

    # Step 1: claim the idempotency key -- short transaction, no network call.
    with transaction.atomic(using="default"):
        try:
            with transaction.atomic(using="default"):
                idem = PaymentIdempotencyKey.objects.create(
                    store=store,
                    key=idempotency_key,
                    request_fingerprint=fingerprint,
                    status=PaymentIdempotencyKey.Status.PENDING,
                )
        except IntegrityError:
            existing = PaymentIdempotencyKey.objects.select_for_update().get(
                store=store, key=idempotency_key
            )
            if existing.request_fingerprint != fingerprint:
                raise IdempotencyConflictError(
                    "This Idempotency-Key was already used for a different payment initiation."
                ) from None
            if existing.status != PaymentIdempotencyKey.Status.COMPLETED:
                raise IdempotencyConflictError(
                    "This Idempotency-Key is still being processed. Retry shortly."
                ) from None
            return PaymentInitiateResult(
                response_status=existing.response_status,
                response_body=existing.response_body,
                created=False,
            )

        if order.status != Order.Status.PENDING_PAYMENT:
            _fail_idempotency_claim(idem, status_code=409, detail="Order is not payable.")
            raise OrderNotPayableError(f"Order {order.number} is {order.status}, not payable.")

        if PaymentIntent.objects.filter(order=order, state=PaymentIntent.State.PROCESSING).exists():
            _fail_idempotency_claim(
                idem, status_code=409, detail="A payment is already in progress for this order."
            )
            raise DuplicateActivePaymentIntentError(
                f"Order {order.number} already has an active payment attempt."
            )

    # Step 2: call the provider -- NO open transaction, no lock held.
    provider = get_provider_for_config(config)
    ctx = PaymentContext(
        order_id=str(order.id),
        amount=order.total_amount,
        currency=order.currency,
        provider_idempotency_key=f"{store.id}:{idempotency_key}",
        metadata={"order_number": order.number},
    )
    result = provider.create_payment(ctx)

    # Step 3: persist -- short transaction, DB only.
    with transaction.atomic(using="default"):
        intent = PaymentIntent.objects.create(
            store=store,
            order=order,
            provider_config=config,
            amount=order.total_amount,
            currency=order.currency,
            state=result.state,
            provider_ref=result.provider_ref,
            idempotency_key=idempotency_key,
            failure_reason=result.failure_reason,
            retryable=result.retryable,
        )
        if result.state == PaymentIntent.State.SUCCEEDED or (
            result.state == PaymentIntent.State.PROCESSING
            and provider.capabilities.confirms_order_on_acceptance
        ):
            # Either genuinely synchronous success, or a COD-shaped provider whose
            # `processing` IS the business commitment to fulfill (approved Phase 9
            # review-round decision -- see apps/payments/providers/manual_cod.py's
            # module docstring). Either way: confirm once, here, at acceptance.
            order_services.confirm_order(order=order)

        body = _intent_body(intent)
        idem = PaymentIdempotencyKey.objects.select_for_update().get(id=idem.id)
        idem.status = PaymentIdempotencyKey.Status.COMPLETED
        idem.response_status = 201
        idem.response_body = body
        idem.save(update_fields=["status", "response_status", "response_body", "updated_at"])

    return PaymentInitiateResult(response_status=201, response_body=body, created=True)


def _fail_idempotency_claim(idem: PaymentIdempotencyKey, *, status_code: int, detail: str) -> None:
    """Completes a claim with an error response so a client retry with the same key
    doesn't hang forever behind `IdempotencyConflictError("still being processed")`."""
    idem.status = PaymentIdempotencyKey.Status.COMPLETED
    idem.response_status = status_code
    idem.response_body = {"detail": detail}
    idem.save(update_fields=["status", "response_status", "response_body", "updated_at"])


def apply_payment_transition(
    *,
    payment_intent_id,
    target_state: str,
    kind: str,
    provider_ref: str,
    amount: int,
    raw_response_redacted: dict | None = None,
    failure_reason: str = "",
    retryable: bool | None = None,
) -> PaymentIntent:
    """
    Must be called inside an open `transaction.atomic()` block by callers
    that already hold whatever else they need locked (webhook processing:
    nothing else; reconciliation: nothing else) -- this function itself
    opens ITS OWN atomic block if none is open yet, so it is also safe to
    call directly. Locks `PaymentIntent` first, `Order` second (via
    `apps.orders.services.confirm_order`/`cancel_order`) -- a single,
    consistent lock order used everywhere in this codebase.
    """
    with transaction.atomic(using="default"):
        intent = PaymentIntent.objects.select_for_update().get(id=payment_intent_id)

        # Audit trail regardless of whether a state change happens -- this is what
        # makes out-of-order/duplicate events visible without ever re-applying
        # side effects for them (approved Phase 9 decision on out-of-order handling).
        PaymentTransaction.objects.create(
            store=intent.store,
            intent=intent,
            kind=kind,
            outcome=(
                PaymentTransaction.Outcome.SUCCEEDED
                if target_state == PaymentIntent.State.SUCCEEDED
                else PaymentTransaction.Outcome.FAILED
            ),
            amount=amount,
            provider_ref=provider_ref,
            raw_response_redacted=raw_response_redacted or {},
        )

        if intent.state in _TERMINAL_STATES:
            # Already resolved -- side effects already applied exactly once. This is
            # the guard that makes re-application safe independent of WebhookEvent
            # uniqueness (approved Phase 9 decision: "لا تعتمد على external_id UNIQUE وحده").
            return intent
        if target_state not in _ALLOWED_TRANSITIONS.get(intent.state, frozenset()):
            # Not a valid transition from the CURRENT state -- logged above, no-op.
            return intent

        intent.state = target_state
        intent.provider_ref = provider_ref or intent.provider_ref
        intent.failure_reason = failure_reason
        intent.retryable = retryable
        intent.save(
            update_fields=["state", "provider_ref", "failure_reason", "retryable", "updated_at"]
        )

        order = Order.objects.select_for_update().get(id=intent.order_id)
        if target_state == PaymentIntent.State.SUCCEEDED:
            if order.status == Order.Status.PENDING_PAYMENT:
                order_services.confirm_order(order=order)
        elif target_state == PaymentIntent.State.FAILED and not retryable:
            if order.status == Order.Status.PENDING_PAYMENT:
                order_services.cancel_order(order=order)
        # target_state == FAILED and retryable: Order stays pending_payment untouched
        # (approved Phase 9 decision -- the reservation is not released either, since
        # `cancel_order` is the only thing that releases it).
        # target_state == CANCELLED: same as a non-retryable failure for Order purposes.
        elif target_state == PaymentIntent.State.CANCELLED:
            if order.status == Order.Status.PENDING_PAYMENT:
                order_services.cancel_order(order=order)

    return intent


def process_webhook(
    *, store: Store, provider_config: StoreProviderConfig, raw_body: bytes, headers: dict
) -> None:
    """
    Order matters (approved Phase 9 decision): `provider_config` is
    resolved by the VIEW from the URL path BEFORE this is even called
    (never from anything inside the body) -- that's what supplies the
    secret this function verifies the signature against. Nothing here
    trusts `store_id`/`order_id`/metadata inside the payload as a
    security boundary; the signature check is the boundary.
    """
    provider = get_provider_for_config(provider_config)
    secret = (
        encryption.decrypt_secret(provider_config.webhook_secret_encrypted)
        if provider_config.webhook_secret_encrypted
        else ""
    )

    try:
        verified = provider.verify_webhook(raw_body=raw_body, headers=headers, secret=secret)
    except SignatureVerificationError as exc:
        raise InvalidWebhookError(str(exc)) from exc

    domain_event = provider.map_event(verified)

    # Claim (provider_config, external_id) -- short transaction, mirrors the
    # Phase 8 idempotency claim pattern but increments `attempts` on a duplicate
    # delivery instead of just replaying a stored response (§8.4: "التكرار ⇒ 200 فورًا").
    with transaction.atomic(using="default"):
        try:
            with transaction.atomic(using="default"):
                event = WebhookEvent.objects.create(
                    store=store,
                    provider_config=provider_config,
                    external_id=domain_event.external_id,
                    signature_valid=True,
                    payload_redacted={"kind": domain_event.kind, "amount": domain_event.amount},
                )
        except IntegrityError:
            existing = WebhookEvent.objects.select_for_update().get(
                provider_config=provider_config, external_id=domain_event.external_id
            )
            existing.attempts += 1
            existing.save(update_fields=["attempts", "updated_at"])
            return  # duplicate delivery -- no reprocessing, no error (200 to the provider)

        intent = _find_intent_for_event(
            store=store, provider_config=provider_config, domain_event=domain_event
        )
        if intent is not None:
            _apply_domain_event(intent=intent, domain_event=domain_event)
        event.processed_at = timezone.now()
        event.save(update_fields=["processed_at", "updated_at"])


def _find_intent_for_event(
    *, store: Store, provider_config: StoreProviderConfig, domain_event
) -> PaymentIntent | None:
    """Correlates by `provider_ref` -- generated locally at `create_payment` time,
    never trusted from the payload as an identity claim on its own (approved Phase 9
    decision: verify tenant/amount/currency below, not just "an id matched")."""
    try:
        return PaymentIntent.objects.get(
            store=store, provider_config=provider_config, provider_ref=domain_event.provider_ref
        )
    except PaymentIntent.DoesNotExist:
        return None


def _apply_domain_event(*, intent: PaymentIntent, domain_event) -> None:
    if intent.amount != domain_event.amount or intent.currency != domain_event.currency:
        # Amount/currency mismatch -- refuse to apply, but the WebhookEvent row
        # above still records the delivery for audit. Never trust a provider event
        # that disagrees with our own authoritative local amount (approved Phase 9
        # decision, point 11 of the original proposal).
        return
    if domain_event.kind not in ("payment_succeeded", "payment_failed"):
        # An event type we don't act on (e.g. Stripe's `payment_intent.created` if a
        # merchant's webhook config sends every event type to us) -- NOT a failure.
        # Recorded via the WebhookEvent row above; no PaymentIntent/Order side effect.
        return
    target_state = (
        PaymentIntent.State.SUCCEEDED
        if domain_event.kind == "payment_succeeded"
        else PaymentIntent.State.FAILED
    )
    apply_payment_transition(
        payment_intent_id=intent.id,
        target_state=target_state,
        kind=PaymentTransaction.Kind.CAPTURE,
        provider_ref=domain_event.provider_ref,
        amount=domain_event.amount,
        raw_response_redacted={"kind": domain_event.kind},
        failure_reason=domain_event.failure_reason,
        retryable=domain_event.retryable,
    )


def capture_manual_cod_payment(*, payment_intent: PaymentIntent) -> PaymentIntent:
    """Dashboard-triggered: "the cash was actually collected" -- distinct from "COD
    was chosen" (already confirmed the Order and fulfilled inventory at acceptance
    time, see `initiate_payment` and apps/payments/providers/manual_cod.py's module
    docstring). This only ever flips `PaymentIntent.state`; `apply_payment_transition`'s
    existing "only act if Order is still pending_payment" guard is what prevents this
    from re-confirming the Order or re-fulfilling inventory -- no new guard needed."""
    if payment_intent.provider_config.provider_key != "manual_cod":
        raise NotManualCodError("This action only applies to manual_cod payment intents.")

    provider = get_provider_for_config(payment_intent.provider_config)
    result = provider.capture(provider_ref=payment_intent.provider_ref)
    target_state = (
        PaymentIntent.State.SUCCEEDED
        if result.outcome == "succeeded"
        else PaymentIntent.State.FAILED
    )
    return apply_payment_transition(
        payment_intent_id=payment_intent.id,
        target_state=target_state,
        kind=PaymentTransaction.Kind.CAPTURE,
        provider_ref=result.provider_ref,
        amount=payment_intent.amount,
        raw_response_redacted=result.raw_response_redacted,
        retryable=result.retryable,
    )
