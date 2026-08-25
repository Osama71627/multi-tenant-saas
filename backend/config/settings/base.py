"""
Shared settings for every environment.

Environment-specific files (local.py / test.py / production.py) import
`from .base import *` and override only what genuinely differs. Nothing
sensitive lives here as a literal value -- everything sensitive is read
via `env()` and has NO default in production.py (it must fail fast if unset).
"""

from datetime import timedelta
from pathlib import Path

import environ
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# .env is optional -- in Docker/production, real environment variables are
# injected directly and no .env file exists on disk.
env_file = BASE_DIR.parent / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["*"])

# Phase 13: the storefront Next.js app server-renders pages, which means
# ITS server (not the shopper's browser) is what calls this API for the
# Host-resolved `/api/v1/storefront/*` surface (apps/stores/middleware.py).
# The shopper's real Host never reaches Django directly for that hop, so
# Django must be told to trust `X-Forwarded-Host` instead of its own
# `Host` header there -- the standard, expected behavior for any app
# sitting behind a reverse proxy (this stack's own Nginx, in production;
# the Next.js server itself, locally) rather than a project-specific
# workaround. `request.get_host()` (what `TenantMiddleware` reads) uses
# `X-Forwarded-Host` automatically once this is on; direct requests
# (curl, the dashboard, webhooks) are unaffected -- none of them set that
# header, so `get_host()` falls back to the real `Host` header exactly as
# before.
USE_X_FORWARDED_HOST = True

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    # Backs refresh-token rotation + reuse detection (docs/ARCHITECTURE.md
    # section 6.2 / docs/DECISIONS.md governance point 2). Its tables are
    # platform-wide, not tenant-owned -- no RLS needed, same as
    # accounts_platformuser.
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "django_structlog",
]

LOCAL_APPS = [
    "apps.core",
    "apps.tenancy",
    "apps.accounts",
    "apps.stores",
    "apps.subscriptions",
    "apps.catalog",
    "apps.inventory",
    "apps.pricing",
    "apps.carts",
    "apps.shipping",
    "apps.orders",
    "apps.payments",
    "apps.notifications",
    "apps.themes",
    "apps.platform_admin",
    "apps.analytics",
    "apps.suppliers",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

AUTH_USER_MODEL = "accounts.PlatformUser"

# --------------------------------------------------------------------------
# Middleware
#
# Order matters. Tenant resolution happens right after security/session
# handling and BEFORE authentication, because tenant resolution must not
# depend on who the user is (see docs/ARCHITECTURE.md section 6).
# request_id is first so every later log line (including security ones)
# carries it.
# --------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "apps.core.middleware.RequestIDMiddleware",
    "django_structlog.middlewares.RequestMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "apps.stores.middleware.TenantMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------
# Database
#
# Two roles, two aliases -- see docs/ARCHITECTURE.md section 2.3 and
# docs/DECISIONS.md. `default` is the role the running application (web +
# celery) authenticates as: NOSUPERUSER, NOBYPASSRLS. `migrator` is the
# schema-owning role used ONLY by `manage.py migrate --database=migrator`
# and by CI. The application must never run business queries through
# `migrator` -- doing so silently bypasses Row-Level Security.
# --------------------------------------------------------------------------
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://app_user:devpass_appuser@127.0.0.1:5432/saas_dev",
    ),
    "migrator": env.db(
        "MIGRATOR_DATABASE_URL",
        default="postgres://app_migrator:devpass_migrator@127.0.0.1:5432/saas_dev",
    ),
    # Phase 14 -- apps.platform_admin ONLY. `app_platform_admin` is
    # BYPASSRLS (see infra/postgres/init/01-roles.sh) but holds only
    # narrow, explicit GRANTs on the specific tables it needs (see
    # apps/platform_admin/apps.py) -- never a blanket "ALL TABLES". No
    # other app may reference this alias; see
    # apps/platform_admin/tests/test_platform_alias_containment.py.
    "platform": env.db(
        "PLATFORM_DATABASE_URL",
        default="postgres://app_platform_admin:devpass_platformadmin@127.0.0.1:5432/saas_dev",
    ),
}
# NOTE: we deliberately do NOT set ATOMIC_REQUESTS here. `TenantMiddleware`
# (apps/tenancy/middleware.py) wraps every request in its own
# `transaction.atomic()` block itself, because it must set the
# transaction-scoped `app.current_store_id` GUC (via `set_config(...,
# is_local=true)`) BEFORE the view runs and have it reliably span the
# whole request. Django's built-in ATOMIC_REQUESTS only wraps the view
# call, not middleware that runs before it, so it can't be used for this.
# Enabling both would just nest a redundant nop savepoint. See
# docs/DECISIONS.md governance point 1.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

DATABASE_ROUTERS = ["apps.tenancy.routers.MigratorRouter"]

# --------------------------------------------------------------------------
# Auth / passwords
# --------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
]

# --------------------------------------------------------------------------
# i18n -- Arabic + English, RTL-ready (per Q1 decision)
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en"
LANGUAGES = [("ar", "Arabic"), ("en", "English")]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# DRF / API
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.tokens.PlatformJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    # Phase 12 pre-implementation check found this half-wired: URLPathVersioning
    # was configured but nothing set `DEFAULT_VERSION`, so
    # `view.versioning_class.default_version` was None. `request.version` was
    # silently always None (harmless -- nothing reads it yet), but
    # drf-spectacular's generator treats `version is None` as "skip this view"
    # for every versioned view -- OpenAPI generation produced ZERO paths, with
    # no warning, discovered only now that Phase 12 actually needs it.
    # Deliberately NOT capturing `<version>` in config/urls.py as an
    # alternative fix: DRF passes URL kwargs straight through to the view
    # handler, so that would inject an unexpected `version` kwarg into every
    # view method's signature project-wide (verified -- it broke ~270 tests
    # across apps with narrow `def post(self, request: Request)` signatures
    # before this safer fix replaced it). "api/v1/..." staying a literal path
    # segment is intentional; this setting alone is the real, low-risk fix,
    # not a new decision -- see docs/ARCHITECTURE.md section 5.2's already-
    # approved "URLPathVersioning -- /api/v1/" policy.
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"auth": "20/min", "store_create": "10/hour"},
    "EXCEPTION_HANDLER": "apps.core.exceptions.rfc9457_exception_handler",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Multi-Tenant SaaS E-Commerce API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    # No "SIGNING_KEY" here on purpose: simplejwt's own default for this
    # setting is `settings.SECRET_KEY`, resolved lazily the first time
    # `api_settings` is accessed (well after Django finishes loading
    # whichever settings module is active). Capturing `SECRET_KEY` into a
    # literal here instead would freeze in *this file's* value even when
    # local.py/test.py/production.py reassign `SECRET_KEY` afterwards --
    # a real bug caught while building Phase 2 (config/settings/test.py's
    # override silently wasn't reaching JWT signing). Don't reintroduce it.
    "AUTH_HEADER_TYPES": ("Bearer",),
    # Claims are intentionally minimal -- permissions are NEVER embedded in
    # the token. See docs/ARCHITECTURE.md section 6.2.
    "USER_ID_CLAIM": "sub",
    "TOKEN_TYPE_CLAIM": "token_type",  # nosec B105 -- a JWT claim *name*, not a secret
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
# django-cors-headers' own default allowlist (content-type, authorization,
# etc.) plus `Idempotency-Key` -- the storefront (Phase 13) sends it on
# every checkout/payment write, cross-origin by design (the storefront
# and this API are always different origins, never same-origin like the
# dashboard's BFF proxy). Without this, the browser's own CORS preflight
# rejects the header before the request is ever sent -- Django-side
# idempotency-key validation never even runs.
CORS_ALLOW_HEADERS = [*default_headers, "idempotency-key"]

# --------------------------------------------------------------------------
# Store provisioning (Phase 3) -- see docs/ARCHITECTURE.md section 6.
# Subdomain-only for now: StoreDomain.hostname = f"{slug}.{PLATFORM_ROOT_DOMAIN}".
# Custom domains are a documented future extension (StoreDomain.Kind.CUSTOM
# already exists), not built yet.
# --------------------------------------------------------------------------
PLATFORM_ROOT_DOMAIN = env("PLATFORM_ROOT_DOMAIN", default="lvh.me")

# --------------------------------------------------------------------------
# Celery
# --------------------------------------------------------------------------
CELERY_BROKER_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_DEFAULT_QUEUE = "default"
# Webhook processing gets its own queue (docs/ARCHITECTURE.md section 8.4,
# section 16 risk #6 "noisy neighbor") so a burst of provider webhooks can
# never starve ordinary request-triggered tasks. Route configured now;
# actually running a worker dedicated to it is a deployment concern (same
# "not verified in this dev environment" caveat as Docker since Phase 1).
CELERY_TASK_ROUTES = {
    "apps.payments.tasks.*": {"queue": "webhooks"},
    # The "email" queue was already provisioned in docker-compose.yml's
    # celery worker command since Phase 0/1 -- Phase 11 is the first to
    # route anything to it.
    "apps.notifications.tasks.*": {"queue": "email"},
    # Forward-looking placeholder, same as the two routes above once were
    # (docs/ARCHITECTURE.md section 13.1: `sync` isolates supplier sync
    # from default/webhooks/email) -- apps.suppliers doesn't exist yet
    # (Phase 16), no-ops harmlessly until it does.
    "apps.suppliers.tasks.*": {"queue": "sync"},
}

# --------------------------------------------------------------------------
# Domain Events (docs/ARCHITECTURE.md line 108: "كل عملية كتابة تُصدر
# Domain Event يُسجَّل في core.EventLog ويُرسل للـ Celery عند الحاجة").
# apps.core.events.emit_domain_event resolves event_type -> consumer
# Celery task NAMES from this plain data mapping -- never a Python
# import -- so a producer (apps.orders today) can trigger a consumer
# (apps.notifications) while staying entirely ignorant that it exists,
# satisfying the "reverse connection via Domain Events only" rule
# (docs/ARCHITECTURE.md section 3) without Django Signals, which are
# explicitly forbidden in critical paths (order/payment/inventory --
# docs/ARCHITECTURE.md line 107).
# --------------------------------------------------------------------------
DOMAIN_EVENT_CONSUMER_TASKS: dict[str, list[str]] = {
    "order.confirmed": ["apps.notifications.tasks.process_domain_event"],
}

# apps.notifications.tasks.recover_unprocessed_domain_events (Phase 11
# review round 2): finds events with no corresponding NotificationDispatch
# via a per-store, RLS-scoped anti-join -- NOT a time cutoff (a hard
# `created_at >= cutoff` WHERE clause would let an event older than this
# window be permanently skipped even though it was never dispatched,
# violating "a committed notification-eligible domain event must not be
# permanently lost merely because the process crashed between DB commit
# and Celery publish"). `NOTIFICATION_RECOVERY_LOOKBACK_HOURS` is kept
# ONLY as an operational staleness threshold -- recovery logs a warning
# when it finds an event older than this, for alerting, but still
# processes it regardless of age. Not a correctness boundary.
NOTIFICATION_RECOVERY_LOOKBACK_HOURS = env.int("NOTIFICATION_RECOVERY_LOOKBACK_HOURS", default=48)

# Per-store cap on how many pending events recover_unprocessed_domain_events
# processes in one sweep -- bounds worst-case work per run (one store with
# a large backlog can't stall the whole sweep); the next scheduled run
# picks up where this one left off (deterministic oldest-first ordering).
NOTIFICATION_RECOVERY_BATCH_SIZE_PER_STORE = env.int(
    "NOTIFICATION_RECOVERY_BATCH_SIZE_PER_STORE", default=200
)

# --------------------------------------------------------------------------
# Payments -- provider credential encryption (docs/ARCHITECTURE.md section
# 8.3). AES-256-GCM, key from env (no KMS in this phase -- approved Phase 9
# decision). `PAYMENT_ENCRYPTION_KEY` is a base64-encoded 32-byte key;
# `PAYMENT_ENCRYPTION_KEY_VERSION` lets a future rotation add a new key
# without invalidating ciphertext already encrypted under an older one.
# --------------------------------------------------------------------------
PAYMENT_ENCRYPTION_KEY = env(
    # dev-only fixed key, never used outside local/test settings in
    # practice -- production sets a real PAYMENT_ENCRYPTION_KEY via env.
    "PAYMENT_ENCRYPTION_KEY",
    default="e7dpmVqzDd/lIeYMjuBG9yLcIKXwhTnc7EoQGHb833U=",
)
PAYMENT_ENCRYPTION_KEY_VERSION = env.int("PAYMENT_ENCRYPTION_KEY_VERSION", default=1)

# --------------------------------------------------------------------------
# Accounts -- MFA TOTP secret encryption (Phase 17, docs/ARCHITECTURE.md
# section 6.3). Same AES-256-GCM envelope shape/rotation story as the
# payment credentials above, its own independent key -- see
# apps.accounts.encryption.
# --------------------------------------------------------------------------
MFA_ENCRYPTION_KEY = env(
    # dev-only fixed key, never used outside local/test settings in
    # practice -- production sets a real MFA_ENCRYPTION_KEY via env.
    "MFA_ENCRYPTION_KEY",
    default="1LgeBKkGaYULer3eI+QOWcjjHjxI0yQ1WBILVmzU6h4=",
)
MFA_ENCRYPTION_KEY_VERSION = env.int("MFA_ENCRYPTION_KEY_VERSION", default=1)

# --------------------------------------------------------------------------
# Cache (also used for tenant-domain resolution cache, rate limiting)
# --------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://127.0.0.1:6379/1"),
    }
}

# --------------------------------------------------------------------------
# Logging -- structured, request_id-correlated, secrets redacted.
# See apps/core/logging.py for the redaction filter.
# --------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_secrets": {"()": "apps.core.logging.SecretRedactionFilter"},
    },
    "formatters": {
        "json": {"()": "apps.core.logging.JSONFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["redact_secrets"],
        },
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django_structlog": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# --------------------------------------------------------------------------
# Tax (Q2 decision: never hard-code a rate -- configuration lives in DB,
# apps.pricing, starting Phase 6. This constant is only the *fallback
# default* offered when a merchant provisions a store in the GCC region.)
# --------------------------------------------------------------------------
DEFAULT_REGION_TAX_HINTS = {
    "SA": {"tax_type": "VAT", "default_rate_percent": "15.00", "currency": "SAR"},
}
