from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-key-change-me")  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://.*\.lvh\.me(:\d+)?$",
    r"^http://lvh\.me(:\d+)?$",
    # Local-dev-only convenience, NOT present in production.py: lets the
    # storefront be exercised via plain localhost/127.0.0.1 (e.g. from a
    # browser automation tool that can't resolve *.lvh.me), in addition
    # to real per-store subdomains. Tenant resolution itself is
    # unaffected -- these still only work if a StoreDomain row for that
    # exact hostname exists (apps/stores/middleware.py); this only
    # widens which ORIGIN header the API will accept the request from.
    r"^http://localhost(:\d+)?$",
    r"^http://127\.0\.0\.1(:\d+)?$",
]
