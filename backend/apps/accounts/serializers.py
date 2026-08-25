from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import PlatformUser


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    full_name = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_email(self, value: str) -> str:
        if PlatformUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class EmailVerifyConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()


class MfaChallengeTokenSerializer(serializers.Serializer):
    challenge_token = serializers.CharField()


class MfaVerifyRequestSerializer(MfaChallengeTokenSerializer):
    code = serializers.CharField()


class MfaEnrollConfirmRequestSerializer(MfaChallengeTokenSerializer):
    code = serializers.CharField()


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformUser
        fields = ["id", "email", "full_name", "is_platform_staff", "email_verified_at"]
        read_only_fields = fields
