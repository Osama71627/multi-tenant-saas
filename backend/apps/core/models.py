from django.db import models

from apps.core.uuid7 import uuid7


class BaseModel(models.Model):
    """
    Root abstract model for every table in the system (tenant-owned or not).

    Primary keys are UUIDv7, generated in Python (see apps/core/uuid7.py),
    never sequential integers -- sequential PKs exposed in a URL let an
    attacker enumerate resources and infer business volume (e.g. "how many
    orders does this store have"). See docs/DECISIONS.md D7.
    """

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class EventLog(BaseModel, TimeStampedModel):
    """
    Append-only domain event log. Every write-side Service call that
    matters for audit/debugging/replay emits one of these. Deliberately
    generic (JSONB payload) so it doesn't couple to any one domain app --
    orders, payments, inventory, and platform-admin all write here without
    apps.core ever importing them (see the import-linter contract in
    pyproject.toml).

    NOT a replacement for the security-focused AuditLog (introduced with
    apps.accounts in Phase 2), which is specifically for "who did what to
    whose store" and has stricter immutability guarantees.
    """

    store_id = models.UUIDField(null=True, blank=True, db_index=True)
    event_type = models.CharField(max_length=255, db_index=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["store_id", "event_type", "-created_at"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M:%S}"
