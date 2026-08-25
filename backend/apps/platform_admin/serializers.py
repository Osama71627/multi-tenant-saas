from __future__ import annotations

from rest_framework import serializers

from apps.accounts.models import PlatformUser
from apps.platform_admin.models import AuditLog
from apps.stores.models import Store
from apps.subscriptions.models import (
    Plan,
    PlanVersion,
    PlanVersionFeature,
    PlanVersionQuota,
    Subscription,
)


class PlatformStoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = [
            "id",
            "name",
            "slug",
            "status",
            "default_currency",
            "contact_email",
            "contact_phone",
            "created_at",
        ]
        read_only_fields = fields


class StoreSuspendRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class PlanVersionFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanVersionFeature
        fields = ["feature_key", "enabled"]


class PlanVersionQuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanVersionQuota
        fields = ["quota_key", "limit"]


class PlanVersionSerializer(serializers.ModelSerializer):
    features = PlanVersionFeatureSerializer(many=True, read_only=True)
    quotas = PlanVersionQuotaSerializer(many=True, read_only=True)

    class Meta:
        model = PlanVersion
        fields = [
            "id",
            "version_number",
            "price_monthly",
            "price_yearly",
            "currency",
            "is_current",
            "published_at",
            "features",
            "quotas",
        ]
        read_only_fields = fields


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id",
            "code",
            "name",
            "is_public",
            "trial_days",
            "grace_period_days",
            "is_default_trial",
            "created_at",
        ]
        read_only_fields = fields


class PlanDetailSerializer(PlanSerializer):
    """`versions` is populated explicitly by the view (a separate,
    correctly-ordered `list_plan_versions` call), not by DRF resolving
    `plan.versions` as a related manager -- see
    apps.platform_admin.views.PlatformPlanDetailView."""

    versions = PlanVersionSerializer(many=True, read_only=True, required=False)

    class Meta(PlanSerializer.Meta):
        fields = [*PlanSerializer.Meta.fields, "versions"]


class PlanCreateRequestSerializer(serializers.Serializer):
    code = serializers.SlugField(max_length=64)
    name = serializers.CharField(max_length=255)
    is_public = serializers.BooleanField(default=True)
    trial_days = serializers.IntegerField(min_value=0, default=0)
    grace_period_days = serializers.IntegerField(min_value=0, default=3)


class PlanVersionPublishRequestSerializer(serializers.Serializer):
    price_monthly = serializers.IntegerField(min_value=0)
    price_yearly = serializers.IntegerField(min_value=0)
    currency = serializers.CharField(max_length=3, default="SAR")
    features = serializers.DictField(child=serializers.BooleanField(), required=False, default=dict)
    quotas = serializers.DictField(
        child=serializers.IntegerField(min_value=0, allow_null=True), required=False, default=dict
    )
    make_current = serializers.BooleanField(default=True)


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_code = serializers.CharField(source="plan_version.plan.code", read_only=True)
    plan_version_number = serializers.IntegerField(
        source="plan_version.version_number", read_only=True
    )

    class Meta:
        model = Subscription
        fields = [
            "id",
            "store_id",
            "status",
            "billing_interval",
            "plan_code",
            "plan_version_number",
            "current_period_start",
            "current_period_end",
            "trial_ends_at",
            "past_due_since",
            "cancel_at",
            "created_at",
        ]
        read_only_fields = fields


class PlatformUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformUser
        fields = [
            "id",
            "email",
            "full_name",
            "is_active",
            "is_platform_staff",
            "email_verified_at",
            "created_at",
        ]
        read_only_fields = fields


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor_user_id",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "store_id",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields
