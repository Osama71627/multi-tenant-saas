from __future__ import annotations

from rest_framework import serializers

from apps.subscriptions.models import (
    PlanVersion,
    PlanVersionFeature,
    PlanVersionQuota,
    Subscription,
    SubscriptionCheckoutSession,
)


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


class PlanVersionFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanVersionFeature
        fields = ["feature_key", "enabled"]
        read_only_fields = fields


class PlanVersionQuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanVersionQuota
        fields = ["quota_key", "limit"]
        read_only_fields = fields


class PublicPlanVersionSerializer(serializers.ModelSerializer):
    """Phase D: the public/authenticated plan-selection screen's data
    source. Real, dynamic PlanVersion data -- price/features/quotas
    are read straight off the DB row the platform admin (via
    `publish_plan_version`/a seed migration) actually published, never
    a value the frontend invents. `features`/`quotas` are nested lists
    (not a single JSON blob) so the frontend can render a real
    checklist without guessing key meanings client-side."""

    plan_code = serializers.CharField(source="plan.code", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    features = PlanVersionFeatureSerializer(many=True, read_only=True)
    quotas = PlanVersionQuotaSerializer(many=True, read_only=True)

    class Meta:
        model = PlanVersion
        fields = [
            "id",
            "plan_code",
            "plan_name",
            "price_monthly",
            "price_yearly",
            "currency",
            "features",
            "quotas",
        ]
        read_only_fields = fields


class SubscriptionCheckoutSessionSerializer(serializers.ModelSerializer):
    """Phase D. `plan_version` is nested (not just an id) so the
    confirmation UI can show the actually-selected plan's real name/
    price without a second request. `theme_preset_id` stays a bare id
    (see models.py's docstring on why `apps.subscriptions` cannot
    resolve it to a name/preview itself) -- the frontend already has
    the full preset list from `GET /api/v1/themes/public/presets` and
    matches it locally."""

    plan_version = PublicPlanVersionSerializer(read_only=True)

    class Meta:
        model = SubscriptionCheckoutSession
        fields = [
            "id",
            "theme_preset_id",
            "plan_version",
            "checkout_status",
            "payment_status",
            "provisioning_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class StartSubscriptionCheckoutSessionSerializer(serializers.Serializer):
    theme_preset_id = serializers.UUIDField(required=False, allow_null=True)


class SelectPlanSerializer(serializers.Serializer):
    plan_version_id = serializers.UUIDField()
