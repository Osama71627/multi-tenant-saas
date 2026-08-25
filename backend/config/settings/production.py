"""
Production settings.

Every value that could leak money, data, or access MUST come from the
environment with NO default here. If it's missing, startup fails loudly
instead of silently running insecurely -- this is deliberate.
"""

from .base import *  # noqa: F403

DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY")  # noqa: F405 -- no default: fail fast if unset
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")  # noqa: F405

DATABASES["default"] = env.db("DATABASE_URL")  # noqa: F405
DATABASES["migrator"] = env.db("MIGRATOR_DATABASE_URL")  # noqa: F405
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)  # noqa: F405

# Real requirement discovered wiring Phase 19's staging topology (Caddy
# terminates TLS, forwards to Django over plain HTTP inside the compose
# network): without this, SECURE_SSL_REDIRECT below can never see a
# request it considers "already secure" -- Django redirects, the proxy
# forwards the redirect target over HTTP again, forever. Caddy sets
# X-Forwarded-Proto on every request it forwards (Caddyfile, `reverse_proxy`
# default behavior) -- this is the standard, documented Django pairing for
# that header, safe specifically BECAUSE nothing except the trusted proxy
# can reach Django directly (it is never bound to a public port itself).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

CORS_ALLOWED_ORIGINS = []  # populated dynamically from StoreDomain, see apps.tenancy (Phase 3+)

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST")  # noqa: F405
EMAIL_PORT = env.int("EMAIL_PORT", default=587)  # noqa: F405
EMAIL_HOST_USER = env("EMAIL_HOST_USER")  # noqa: F405
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")  # noqa: F405
EMAIL_USE_TLS = True

SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
if SENTRY_DSN:
    import sentry_sdk

    # `environment` distinguishes staging from production in the Sentry UI
    # (staging.py inherits this whole block and overrides the default --
    # see that file). `release` ties every reported error back to the
    # exact commit that produced the running image -- set by whatever
    # started the container (infra/build-images.sh prints the short SHA
    # it tagged; the deploy step is responsible for passing it through as
    # RELEASE_VERSION), never computed by shelling out to git here: the
    # runtime image has neither a `.git` directory (never copied in) nor
    # the git binary installed, so that would always fail.
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=env("SENTRY_ENVIRONMENT", default="production"),  # noqa: F405
        release=env("RELEASE_VERSION", default="unknown"),  # noqa: F405
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
