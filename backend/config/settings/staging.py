"""
Staging settings.

Extends production.py -- every locked security decision from Phases 1-18
(RLS roles, MFA, CSP baseline, cookie/HSTS hardening, fail-fast secrets)
stays exactly as production defines it. This file only adjusts the two
things that are genuinely environment-specific to the Phase 19 staging
topology (Caddy in front, mailhog as the SMTP catcher) rather than
security posture.
"""

from .production import *  # noqa: F403

# mailhog (this project's existing local/staging SMTP catcher) has no TLS
# listener. production.py hardcodes EMAIL_USE_TLS=True for real providers;
# staging talks to mailhog instead, so this is an environment fact, not a
# security downgrade -- nothing about payment/session/auth data flows
# through this path.
EMAIL_USE_TLS = False

# Real failure found running this for real: the dashboard/platform-admin
# BFFs (and the container's own :8000 HEALTHCHECK) call Django directly
# over plain HTTP inside the Docker network (BACKEND_INTERNAL_URL=
# http://backend:8000, by design -- see @saas/auth/backend.ts), never
# through Caddy. With SECURE_SSL_REDIRECT=True, Django saw those requests
# as insecure (no X-Forwarded-Proto, because there's no proxy in that
# path at all) and 301-redirected them to https://backend:8000/... -- a
# port that only ever speaks plain HTTP, so the BFF's fetch just hung
# until it timed out. This is not a security downgrade: `backend` has no
# `ports:` published in docker-compose.staging.yml, so it is UNREACHABLE
# from outside the Docker network by construction -- Caddy (which DOES
# forward X-Forwarded-Proto: https, see infra/caddy/Caddyfile) is the
# only externally reachable path in, and it terminates real TLS. The
# redirect was only ever firing on trusted, internal, network-isolated
# traffic that was never insecure in the first place.
SECURE_SSL_REDIRECT = False

# production.py deliberately ships CORS_ALLOWED_ORIGINS = [] (a real
# deployment sets explicit origins per merchant custom domain -- see that
# file's comment). Staging instead uses the SAME *.lvh.me wildcard-
# subdomain-per-store convention as local.py's CORS_ALLOWED_ORIGIN_REGEXES
# -- this is that same local-dev pattern, over https instead of http
# (Caddy's real TLS), not a new decision. Real bug found running this for
# real: the storefront's browser-side cart/checkout fetches (cross-origin
# by design, see base.py's Idempotency-Key comment) were CORS-rejected
# with no CORS_ALLOWED_ORIGINS/regex configured for staging at all.
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.lvh\.me(:\d+)?$",
    r"^https://lvh\.me(:\d+)?$",
]
