"""
Phase 14 -- Platform Admin. See apps/platform_admin/apps.py for the DB
role/alias architecture (approved decision: separate BYPASSRLS role +
DB alias, no RLS policy changes, no generic bypass helper).
"""

from __future__ import annotations

from django.db import models

from apps.core.models import BaseModel, TimeStampedModel


class AuditLog(BaseModel, TimeStampedModel):
    """
    Append-only record of every privileged action taken through
    `apps.platform_admin`. Real immutability, not just convention: this
    table's RLS policy (see migrations/0001_initial.py,
    `apps.tenancy.rls.platform_admin_only_policy_sql`) has zero policies
    for any command, and `app_platform_admin`'s own GRANTs (apps.py)
    are SELECT + INSERT only -- no role, including the platform role
    itself, can UPDATE or DELETE a row here through ordinary application
    traffic.

    Deliberately NOT a `TenantOwnedModel` -- an action can be platform-
    global (e.g. creating a Plan) with no single owning store, so
    `store_id` is a plain nullable field, populated whenever the action
    genuinely was store-scoped, not a tenancy-enforced FK.
    """

    actor_user_id = models.UUIDField()
    actor_email = models.EmailField(
        help_text="Denormalized at write time -- readable without a second "
        "cross-role join, and stable even if the actor account is later renamed."
    )
    action = models.CharField(max_length=100, db_index=True)
    target_type = models.CharField(max_length=50, db_index=True)
    target_id = models.UUIDField()
    store_id = models.UUIDField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Safe, non-secret context only -- never tokens/passwords/payment data.",
    )

    class Meta:
        db_table = "platform_admin_auditlog"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_type", "target_id", "-created_at"]),
            models.Index(fields=["store_id", "-created_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.action} on {self.target_type}:{self.target_id} by {self.actor_email}"
