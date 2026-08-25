"""
Registers `PlatformJWTAuthentication` with drf-spectacular's OpenAPI
generator. drf-spectacular ships a built-in extension for SimpleJWT's own
`JWTAuthentication`, but extension lookup matches by exact class path
(not `isinstance`) -- `PlatformJWTAuthentication` (apps/accounts/tokens.py)
subclasses it to enforce the `aud: "platform"` realm claim, which makes it
a different class the built-in extension never matches. Every dashboard/
auth endpoint uses this authenticator, so without this the generated
schema's `security` field silently omits the bearer-auth requirement on
literally every authenticated operation -- found while fixing the
Phase 12 pre-implementation OpenAPI generation gap (see the settings.py
comment next to REST_FRAMEWORK["DEFAULT_VERSION"] for that other half).

Imported from `AccountsConfig.ready()` -- drf-spectacular's extension
registry is populated by import side-effect, so this module has to
actually run once, not just exist.
"""

from __future__ import annotations

from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class PlatformJWTScheme(SimpleJWTScheme):
    target_class = "apps.accounts.tokens.PlatformJWTAuthentication"
    name = "platformJwtAuth"
