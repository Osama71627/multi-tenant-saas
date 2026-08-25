from __future__ import annotations

from rest_framework import serializers

from apps.subscriptions.models import Subscription


class SubscriptionStatusSerializer(serializers.ModelSerializer):
    """Phase 12 (dashboard subscription-status UI). Read-only -- writes
    to Subscription remain `apps.subscriptions.services.upgrade_subscription`/
    `schedule_downgrade`, not exposed over HTTP yet (no reviewed
    self-service upgrade/downgrade UI architecture exists, approved
    Phase 10 technical debt, docs/PHASE_10_REPORT.md)."""

    plan_code = serializers.CharField(source="plan_version.plan.code", read_only=True)
    plan_name = serializers.CharField(source="plan_version.plan.name", read_only=True)
    price_monthly = serializers.IntegerField(source="plan_version.price_monthly", read_only=True)
    price_yearly = serializers.IntegerField(source="plan_version.price_yearly", read_only=True)
    currency = serializers.CharField(source="plan_version.currency", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "status",
            "billing_interval",
            "current_period_start",
            "current_period_end",
            "trial_ends_at",
            "cancel_at",
            "plan_code",
            "plan_name",
            "price_monthly",
            "price_yearly",
            "currency",
        ]
        read_only_fields = fields
