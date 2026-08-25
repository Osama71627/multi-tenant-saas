"""
JWT for the Platform identity realm (docs/ARCHITECTURE.md section 6.2 /
docs/DECISIONS.md governance point 2):

  * `aud: "platform"` on every token issued here -- rejected by
    `PlatformJWTAuthentication` if missing/wrong, so a token from some
    other realm (the future `storefront`/customer realm, once
    apps.customers exists) can never authenticate as a platform user.
  * NO permissions/role claims embedded -- see `PlatformUser`-side
    docstrings and apps/accounts/permissions_catalog.py; authorization is
    always resolved fresh from the DB.
  * Rotating refresh tokens (`ROTATE_REFRESH_TOKENS`) + blacklist-on-
    rotation are configured in SIMPLE_JWT (config/settings/base.py) and
    give free single-token reuse *rejection* via
    `rest_framework_simplejwt.token_blacklist`. What that does NOT give
    you is *family* invalidation: if an attacker steals a refresh token
    and the legitimate user's next rotation happens first, the attacker's
    later replay of the (now-blacklisted) stolen token is rejected -- but
    the attacker's own already-rotated descendant tokens, if they got a
    rotation in first, would otherwise stay valid. `PlatformTokenRefreshSerializer`
    below closes that gap: ANY blacklisted-token reuse blacklists every
    outstanding token for that user, forcing a full re-login everywhere.
"""

from __future__ import annotations

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

TOKEN_AUDIENCE = "platform"  # noqa: S105 # nosec B105 -- a JWT `aud` claim value, not a secret


def blacklist_all_outstanding_tokens_for_user(user_id) -> None:
    """
    Shared by refresh-reuse family invalidation (below) and
    apps.accounts.services.confirm_password_reset (a password reset must
    also kill every other active session -- docs/ARCHITECTURE.md section
    6.3). `bulk_create` + a pre-check set, not `get_or_create` in a loop,
    to keep this O(1) queries instead of O(n) for a user with many
    sessions.
    """
    outstanding_ids = OutstandingToken.objects.filter(user_id=user_id).values_list("id", flat=True)
    already_blacklisted = set(
        BlacklistedToken.objects.filter(token_id__in=outstanding_ids).values_list(
            "token_id", flat=True
        )
    )
    BlacklistedToken.objects.bulk_create(
        [
            BlacklistedToken(token_id=token_id)
            for token_id in outstanding_ids
            if token_id not in already_blacklisted
        ]
    )


class PlatformTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["aud"] = TOKEN_AUDIENCE
        # `False` by default: this serializer only ever mints tokens
        # directly (via LoginView) for non-platform-staff accounts, whose
        # tokens never need to carry a completed-MFA claim. Platform-staff
        # tokens are minted exclusively by apps.accounts.mfa_services'
        # verify/enroll-confirm flow, which builds on this same token and
        # explicitly overwrites this claim to True only after a second
        # factor succeeds -- see IsPlatformStaff (apps.platform_admin.
        # permissions), which checks this claim, not just the live DB flag,
        # precisely so an old token can't ride a later staff promotion in.
        token["mfa"] = False
        return token


class PlatformTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except TokenError as exc:
            self._invalidate_family_if_identifiable(attrs["refresh"])
            raise InvalidToken(str(exc)) from exc

    @staticmethod
    def _invalidate_family_if_identifiable(raw_token: str) -> None:
        """
        Best-effort: decode the presented token's SIGNATURE-VERIFIED
        payload (bypassing `RefreshToken.verify()`, which is exactly
        where the blacklist check that just failed lives) to recover the
        user id, then blacklist every OutstandingToken that user has.

        Security-critical detail: this calls the low-level
        `token_backend.decode(raw_token, verify=True)` directly rather
        than `RefreshToken(raw_token, verify=False)`. The latter's
        `verify=False` disables the JWT SIGNATURE check too (it's passed
        straight through to `verify_signature`), which would let anyone
        submit an unsigned, hand-crafted token carrying an arbitrary
        `user_id` claim and force-logout ANY user of their choosing --
        a self-inflicted account-lockout DoS. `verify=True` here checks
        signature + expiry but, critically, does NOT invoke the blacklist
        check (that only happens inside `Token.verify()`, which this
        bypasses on purpose) -- so a legitimately-issued-but-now-
        blacklisted token still decodes fine, while a forged one is
        rejected before any user id is ever trusted.
        """
        try:
            # simplejwt's own type hint for `decode()` names the arg type
            # as its `Token` class, but the implementation just hands it
            # straight to PyJWT, which wants str/bytes -- this is a
            # library stub inaccuracy (a plain string is exactly right
            # here and at every other call site in the codebase).
            decoded = token_backend.decode(raw_token, verify=True)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 - any decode failure means "can't attribute, skip"
            return

        user_id = decoded.get(api_settings.USER_ID_CLAIM)
        if not user_id:
            return
        blacklist_all_outstanding_tokens_for_user(user_id)


class PlatformJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        validated_token = super().get_validated_token(raw_token)
        if validated_token.get("aud") != TOKEN_AUDIENCE:
            raise InvalidToken("Token audience mismatch: expected the platform realm.")
        return validated_token
