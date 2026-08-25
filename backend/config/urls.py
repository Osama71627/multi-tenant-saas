import logging

from django.contrib import admin
from django.core.cache import cache
from django.db import connections
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

logger = logging.getLogger(__name__)


def healthz(request):
    """Liveness probe -- does not touch the database."""
    return JsonResponse({"status": "ok"})


def readyz(request):
    """Readiness probe -- confirms the dependencies needed to safely take
    traffic are reachable. Deliberately shallow: a boolean per dependency,
    never connection strings, hostnames, or exception detail in the
    RESPONSE (those belong in logs, not in an endpoint any load balancer
    can hit unauthenticated) -- but a failure is still logged server-side,
    so an operator investigating a 503 isn't left guessing.
    """
    checks = {"database": False, "cache": False}

    try:
        connections["default"].cursor().close()
        checks["database"] = True
    except Exception:
        logger.warning("readyz: database check failed", exc_info=True)

    try:
        sentinel = object()
        cache.set("readyz-probe", "ok", timeout=5)
        checks["cache"] = cache.get("readyz-probe", sentinel) == "ok"
    except Exception:
        logger.warning("readyz: cache check failed", exc_info=True)

    ready = all(checks.values())
    status = "ok" if ready else "unavailable"
    return JsonResponse({"status": status, "checks": checks}, status=200 if ready else 503)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("readyz", readyz),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # The 4 API surfaces (auth/platform/dashboard/storefront) are wired up
    # as their apps land. See docs/ARCHITECTURE.md section 5. "v1" is a
    # literal path segment, NOT a captured `<version>` kwarg on purpose --
    # see the REST_FRAMEWORK["DEFAULT_VERSION"] comment in
    # config/settings/base.py for why capturing it would break every
    # existing view's call signature project-wide, and why a plain
    # `default_version` fallback is the correct, safe fix instead.
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.stores.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.inventory.urls")),
    path("api/v1/", include("apps.pricing.urls")),
    path("api/v1/", include("apps.carts.urls")),
    path("api/v1/", include("apps.shipping.urls")),
    path("api/v1/", include("apps.orders.urls")),
    path("api/v1/", include("apps.payments.urls")),
    path("api/v1/", include("apps.themes.urls")),
    path("api/v1/", include("apps.subscriptions.urls")),
    path("api/v1/", include("apps.platform_admin.urls")),
    path("api/v1/", include("apps.analytics.urls")),
    path("api/v1/", include("apps.suppliers.urls")),
]
