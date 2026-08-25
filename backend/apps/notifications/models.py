"""
Phase 11 -- Notifications. Full decision record in docs/PHASE_11_REPORT.md;
summary of the load-bearing ones:

1. `NotificationTemplate` is platform-global (no `store_id`) -- approved
   architecture decision, same shape as Phase 10's `Plan`/`PlanVersion`:
   RLS enabled with only an open `SELECT` policy
   (`apps.tenancy.rls.global_readonly_policy_sql`). `app_user` has no
   write policy on it at all; publishing/editing templates happens only
   via `app_migrator` (migration/fixture/the
   `publish_notification_template` management command -- never a
   runtime service function, matching Phase 10's `publish_plan_version`
   boundary).

2. `NotificationDispatch` is tenant-owned, standard RLS -- it is the
   ONLY place delivery/idempotency/retry state lives. `apps.core.EventLog`
   stays a pure durable audit record; it is never mutated to track
   "was this sent" (approved review-round decision: EventLog must not
   become a mutable job queue or a second source of truth for delivery
   state).
"""

from __future__ import annotations

from django.db import models

from apps.core.models import BaseModel, TimeStampedModel
from apps.tenancy.models import TenantOwnedModel


class NotificationTemplate(BaseModel, TimeStampedModel):
    """One row per (key, locale) -- e.g. ("order_confirmation", "en").
    `body_text` uses `string.Template` (`$name`) placeholders only --
    see apps/notifications/rendering.py for why: flat substitution
    cannot execute attribute/method access, so a template body can never
    reach into anything beyond the exact allowlisted context keys a
    Service explicitly builds for it."""

    key = models.CharField(max_length=64)
    locale = models.CharField(max_length=8)
    subject = models.CharField(max_length=255)
    body_text = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "notifications_notificationtemplate"
        constraints = [
            models.UniqueConstraint(fields=["key", "locale"], name="uniq_template_key_locale"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.key} ({self.locale})"


class NotificationDispatch(TenantOwnedModel):
    """
    Durable claim + delivery/idempotency/retry state for ONE logical
    notification derived from ONE domain event. `(store, event, channel,
    notification_type)` uniqueness is what makes "the same order.confirmed
    event processed N times" collapse to exactly one logical dispatch --
    same `try: create() / except IntegrityError: get()` shape as every
    other idempotency table in this project (`IdempotencyKey`,
    `PaymentIdempotencyKey`, Phase 10's `UsageRecord`).
    """

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        # Terminal, never retried: bad recipient, template/render error.
        FAILED = "failed", "Failed"
        # Terminal, never retried: exhausted retries on a TRANSIENT error
        # (e.g. repeated SMTP timeouts). Distinct from FAILED so operators
        # can tell "this will never work" apart from "this kept timing out".
        DEAD_LETTER = "dead_letter", "Dead letter"

    event = models.ForeignKey("core.EventLog", on_delete=models.PROTECT, related_name="+")
    notification_type = models.CharField(max_length=64)
    channel = models.CharField(max_length=32, choices=Channel.choices)
    # Snapshotted at claim time from the authoritative source (e.g.
    # `Order.email`) -- approved decision: recipient is NEVER re-derived
    # from Customer/Cart/webhook metadata/request payload, only from the
    # historical record the event refers to.
    recipient = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications_notificationdispatch"
        constraints = [
            models.UniqueConstraint(
                fields=["store", "event", "channel", "notification_type"],
                name="uniq_dispatch_per_event_channel",
            ),
        ]
        indexes = [models.Index(fields=["store", "status"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.notification_type}/{self.channel} for event {self.event_id} ({self.status})"
