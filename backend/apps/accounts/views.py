from __future__ import annotations

from rest_framework import exceptions, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts import lockout, mfa_services, services
from apps.accounts.models import PlatformUser
from apps.accounts.serializers import (
    EmailVerifyConfirmSerializer,
    MeSerializer,
    MfaChallengeTokenSerializer,
    MfaEnrollConfirmRequestSerializer,
    MfaVerifyRequestSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
)
from apps.accounts.services import EmailVerificationError, PasswordResetError
from apps.accounts.tokens import PlatformTokenObtainPairSerializer, PlatformTokenRefreshSerializer


def _client_ip(request: Request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _issue_mfa_verified_tokens(user: PlatformUser) -> dict[str, str]:
    """Mints a token pair carrying `mfa=True` -- the ONLY code path that
    ever sets that claim (see apps.accounts.tokens' docstring on why
    IsPlatformStaff checks it, not just the live DB flag)."""
    token = PlatformTokenObtainPairSerializer.get_token(user)
    token["mfa"] = True
    return {"refresh": str(token), "access": str(token.access_token)}


def _looks_like_recovery_code(code: str) -> bool:
    # Recovery codes are always issued as "xxxxx-xxxxx" (apps.accounts.mfa);
    # TOTP codes are 6 plain digits -- a hyphen unambiguously means "this
    # is a recovery code", never a false positive against a real TOTP code.
    return "-" in code


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.register_user(**serializer.validated_data)
        return Response(MeSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    """
    Wraps SimpleJWT's TokenObtainPairView with the brute-force lockout
    from apps.accounts.lockout -- locked on (email, IP), see that
    module's docstring for why.

    Phase 17: a platform-staff account (`is_platform_staff=True`) never
    gets a JWT from this endpoint directly -- see `_platform_staff_login`
    below and `apps.accounts.mfa_services`' module docstring for the full
    two-step design. Ordinary accounts are completely unaffected and keep
    the exact single-step flow this view always had.
    """

    # simplejwt's TokenViewBase declares `permission_classes = ()`, which
    # mypy infers as the literal type `tuple[()]` rather than the usual
    # `list[type[BasePermission]]` -- a known stub-inference quirk, not a
    # real incompatibility (DRF accepts any sequence here at runtime).
    permission_classes = [permissions.AllowAny]  # type: ignore[assignment]
    serializer_class = PlatformTokenObtainPairSerializer
    throttle_scope = "auth"

    def post(self, request: Request, *args, **kwargs) -> Response:
        email = str(request.data.get("email", ""))
        password = str(request.data.get("password", ""))
        ip = _client_ip(request)

        if email and lockout.is_locked_out(email, ip):
            return Response(
                {
                    "type": "AccountLocked",
                    "title": "Too many failed login attempts.",
                    "status": status.HTTP_429_TOO_MANY_REQUESTS,
                    "detail": "Try again later.",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        candidate = PlatformUser.objects.filter(email__iexact=email).first() if email else None
        if candidate is not None and candidate.is_platform_staff:
            return self._platform_staff_login(user=candidate, password=password, email=email, ip=ip)

        # DRF's exception flow means a failed login doesn't return here at
        # all -- `TokenObtainPairView.post()` raises `AuthenticationFailed`
        # (via `serializer.is_valid(raise_exception=True)`), and that
        # exception propagates straight past the rest of this method up to
        # `dispatch()`'s handler, which is what actually turns it into the
        # 401 response. So the failure counter has to be registered in the
        # `except` branch, not inferred from a response that's never built
        # here -- re-raising afterwards preserves the normal 401 behavior.
        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            if email:
                lockout.register_failure(email, ip)
            raise

        if email:
            if response.status_code == status.HTTP_200_OK:
                lockout.clear_failures(email, ip)
            else:
                lockout.register_failure(email, ip)
        return response

    @staticmethod
    def _platform_staff_login(
        *, user: PlatformUser, password: str, email: str, ip: str
    ) -> Response:
        """No JWT is issued here, ever -- only an opaque, short-lived
        `MfaChallenge` token. `MfaVerifyView`/`MfaEnrollConfirmView` are the
        only places a platform-staff JWT is minted, and only after a
        second factor succeeds."""
        if not user.is_active or not user.check_password(password):
            lockout.register_failure(email, ip)
            raise exceptions.AuthenticationFailed(
                "No active account found with the given credentials"
            )
        lockout.clear_failures(email, ip)
        _challenge, raw_token = mfa_services.issue_login_challenge(user)
        return Response(
            {"state": mfa_services.enrollment_state(user), "challenge_token": raw_token},
            status=status.HTTP_200_OK,
        )


class RefreshView(TokenRefreshView):
    # See the comment on LoginView.permission_classes above.
    permission_classes = [permissions.AllowAny]  # type: ignore[assignment]
    serializer_class = PlatformTokenRefreshSerializer
    throttle_scope = "auth"


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request) -> Response:
        raw_refresh = request.data.get("refresh")
        if not raw_refresh:
            return Response({"detail": "refresh is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(raw_refresh).blacklist()
        except TokenError as exc:
            raise InvalidToken(str(exc)) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_password_reset(email=serializer.validated_data["email"])
        # Same response regardless of whether the email exists -- see
        # apps/accounts/services.py:request_password_reset docstring.
        return Response(
            {"detail": "If an account with this email exists, a reset link has been sent."}
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.confirm_password_reset(
                token=serializer.validated_data["token"],
                new_password=serializer.validated_data["new_password"],
            )
        except PasswordResetError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Password has been reset."})


class EmailVerifyResendView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        # IsAuthenticated guarantees this at runtime; `assert` would do
        # the same type-narrowing for mypy but gets stripped under `-O`
        # (bandit B101) -- an explicit check survives that and is the
        # same number of lines.
        if not isinstance(request.user, PlatformUser):
            raise exceptions.PermissionDenied("Authenticated user is not a PlatformUser.")
        if request.user.email_verified_at is not None:
            return Response({"detail": "Email is already verified."})
        services.send_email_verification(request.user)
        return Response({"detail": "Verification email sent."})


class EmailVerifyConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        serializer = EmailVerifyConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.confirm_email_verification(token=serializer.validated_data["token"])
        except EmailVerificationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Email verified."})


class MfaVerifyView(APIView):
    """Second step of platform-staff login for an already-enrolled device:
    {challenge_token, code} -> full JWT (mfa=True). `code` may be a 6-digit
    TOTP code or a recovery code (see `_looks_like_recovery_code`)."""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        serializer = MfaVerifyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_challenge_token = serializer.validated_data["challenge_token"]
        code = serializer.validated_data["code"]
        try:
            if _looks_like_recovery_code(code):
                user = mfa_services.verify_recovery_code_login(
                    raw_challenge_token=raw_challenge_token, code=code
                )
            else:
                user = mfa_services.verify_totp_login(
                    raw_challenge_token=raw_challenge_token, code=code
                )
        except mfa_services.MfaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(_issue_mfa_verified_tokens(user))


class MfaEnrollStartView(APIView):
    """First step of enrollment (only reachable with a valid challenge from
    a login that returned `state: mfa_setup_required`): generates a
    pending TOTP secret and returns it for manual entry into an
    authenticator app, plus the equivalent `otpauth://` URI."""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        serializer = MfaChallengeTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            _device, secret, uri = mfa_services.enroll_start(
                raw_challenge_token=serializer.validated_data["challenge_token"]
            )
        except mfa_services.MfaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({"secret": secret, "provisioning_uri": uri})


class MfaEnrollConfirmView(APIView):
    """Second step of enrollment: {challenge_token, code} -> confirms the
    pending device, issues one-time recovery codes (returned RAW here,
    exactly once), and completes login with a full JWT (mfa=True)."""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        serializer = MfaEnrollConfirmRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user, recovery_codes = mfa_services.enroll_confirm(
                raw_challenge_token=serializer.validated_data["challenge_token"],
                code=serializer.validated_data["code"],
            )
        except mfa_services.MfaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        tokens = _issue_mfa_verified_tokens(user)
        return Response({**tokens, "recovery_codes": recovery_codes})


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        # No cross-store membership list here on purpose -- see
        # docs/PHASE_2_REPORT.md "scope decision: /auth/me stays
        # platform-identity-only". Listing "which stores am I a member
        # of" is a genuinely cross-tenant read; doing it correctly needs
        # either a dedicated platform-level DB role (deferred to
        # apps.platform_admin) or a second RLS GUC dimension layered on
        # top of Phase 1's tenant GUC -- both real architectural
        # decisions deliberately not made in passing here.
        return Response(MeSerializer(request.user).data)
