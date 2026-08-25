from __future__ import annotations

from rest_framework import serializers

from apps.payments import encryption
from apps.payments.models import StoreProviderConfig
from apps.payments.providers.registry import PROVIDER_KEYS


class PaymentInitiateRequestSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    provider_key = serializers.ChoiceField(choices=PROVIDER_KEYS)


class StorefrontProviderSerializer(serializers.Serializer):
    """Phase 13 checkout's payment-method picker needs to know WHICH
    providers this store actually accepts -- never anything else
    (`credentials_hint`/`mode`/`public_metadata` are merchant-only)."""

    provider_key = serializers.CharField()


class PaymentIntentResponseSerializer(serializers.Serializer):
    """Documents the exact plain-dict shape `apps.payments.services._intent_body`
    already returns -- for `@extend_schema` typing only, never constructed
    or validated against directly (the view returns the service's dict as-is)."""

    id = serializers.UUIDField()
    order_id = serializers.UUIDField()
    state = serializers.CharField()
    amount = serializers.IntegerField()
    currency = serializers.CharField()
    provider_key = serializers.CharField()


class StoreProviderConfigSerializer(serializers.ModelSerializer):
    """`credentials`/`webhook_secret` are write-only (docs/ARCHITECTURE.md section
    8.3: "لا endpoint يعيد السر إطلاقًا") -- never round-tripped back out. Reading
    a config only ever shows `credentials_hint`, computed once at write time."""

    credentials = serializers.CharField(write_only=True, required=False, allow_blank=True)
    webhook_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = StoreProviderConfig
        fields = [
            "id",
            "provider_key",
            "mode",
            "is_enabled",
            "credentials_hint",
            "public_metadata",
            "credentials",
            "webhook_secret",
        ]
        read_only_fields = ["id", "credentials_hint"]

    def create(self, validated_data):
        credentials = validated_data.pop("credentials", "")
        webhook_secret = validated_data.pop("webhook_secret", "")
        if credentials:
            validated_data["credentials_encrypted"] = encryption.encrypt_secret(credentials)
            validated_data["credentials_hint"] = encryption.mask_secret(credentials)
        if webhook_secret:
            validated_data["webhook_secret_encrypted"] = encryption.encrypt_secret(webhook_secret)
        return super().create(validated_data)
