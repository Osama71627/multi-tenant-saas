import uuid

import structlog

logger = structlog.get_logger(__name__)

_API_CSP = (
    "default-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'"
)

# Django's own /admin/ site is a first-party, staff-only fallback tool
# (docs/ARCHITECTURE.md's real Phase 14 admin surface is
# apps.platform_admin's Next.js app, which gets a full nonce-based CSP --
# see frontend/packages/auth/src/csp.ts). Its templates render no
# attacker-controlled HTML (Django auto-escapes everywhere) but DO use a
# handful of inline <script>/<style> tags baked into Django itself --
# nonce-threading those would mean patching Django's own admin templates,
# out of proportion to the actual risk on a tool this project doesn't
# treat as the reviewed product surface. This is the one deliberate,
# narrowly-scoped exception (admin only, never the API), documented per
# the Phase 17 approved CSP policy.
_ADMIN_CSP = (
    "default-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'"
)

_PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=()"


class SecurityHeadersMiddleware:
    """Content-Security-Policy + Permissions-Policy on every Django
    response (docs/ARCHITECTURE.md section 12's Headers row) -- the
    remaining headers in that row (HSTS, X-Content-Type-Options,
    Referrer-Policy, X-Frame-Options) already come from Django's own
    `SecurityMiddleware`/`XFrameOptionsMiddleware` + settings, see
    config/settings/production.py."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        is_admin = request.path.startswith("/admin/")
        response["Content-Security-Policy"] = _ADMIN_CSP if is_admin else _API_CSP
        response["Permissions-Policy"] = _PERMISSIONS_POLICY
        return response


class RequestIDMiddleware:
    """
    Stamps every request with a correlation id (`request.request_id`),
    echoes it back as `X-Request-Id`, and binds it into structlog's
    contextvars so every log line emitted while handling this request
    carries it automatically -- including lines from deep inside a Service
    or a Celery task dispatched from this request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-Id")
        request.request_id = incoming or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request.request_id)
        try:
            response = self.get_response(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response["X-Request-Id"] = request.request_id
        return response
