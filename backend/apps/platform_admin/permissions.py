"""
The real security boundary for every `/api/v1/platform/*` endpoint --
approved Phase 14 constraint: hiding a route in the frontend is not
enough, the backend permission check is what actually matters. See
apps/platform_admin/tests/test_permissions.py for the required proof
(non-staff gets 403 and no privileged query ever runs).

Phase 17: also requires the presented token's `mfa` claim to be `True`
(set only by `apps.accounts.mfa_services`' verify/enroll-confirm flow,
never by a plain password login -- see `apps.accounts.tokens`). This is
deliberately a TOKEN check, not just a live `user.is_platform_staff`
check: an access token minted before an account was promoted to platform
staff never carries `mfa=True`, so it stays rejected here until the user
logs out and back in through the full MFA flow -- closing the
"promoted mid-session" gap called out in docs/PHASE_17_REPORT.md.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import Token

from apps.accounts.models import PlatformUser


class IsPlatformStaff(BasePermission):
    message = "This action requires platform staff access with completed MFA."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not (
            isinstance(user, PlatformUser)
            and user.is_authenticated
            and user.is_active
            and user.is_platform_staff
        ):
            return False
        # DRF's own stub types `request.auth` as `Token | Any`, where that
        # `Token` is `rest_framework.authtoken.models.Token` -- DRF's
        # unrelated legacy token-auth model, not simplejwt's. This project
        # never uses authtoken, so the real runtime type here is always
        # simplejwt's `Token` (MutableMapping-backed, supports `.get()`);
        # this isinstance check both narrows mypy correctly (no `Any`
        # needed) and is a genuinely stronger runtime check than a bare
        # `is not None`.
        token = request.auth
        return isinstance(token, Token) and token.get("mfa") is True
