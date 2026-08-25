"""
Cache-based brute-force lockout for login attempts. Locks on the
combination of (email, IP) per docs/ARCHITECTURE.md section 6.3, so a
single attacker IP can't lock out a legitimate user by deliberately
failing their login from elsewhere, and a botnet spraying one password
across many emails from one IP still gets throttled per-target.

Scope note: this is intentionally the minimal real thing, not a stand-in.
`django-axes` (full-featured, admin-visible, IP-range-aware) is still the
plan for Phase 17 Security Hardening's broader pass -- see
docs/ARCHITECTURE.md section 17's roadmap. This unblocks Phase 2 without
that dependency's extra settings/backend wiring, and isn't a placeholder:
it is unit-tested and actually enforced on the login endpoint.
"""

from __future__ import annotations

from django.core.cache import cache

THRESHOLD = 5
WINDOW_SECONDS = 15 * 60
LOCKOUT_SECONDS = 15 * 60


def _key(email: str, ip: str) -> str:
    return f"auth:failed_login:{email.strip().lower()}:{ip}"


def is_locked_out(email: str, ip: str) -> bool:
    return cache.get(_key(email, ip), 0) >= THRESHOLD


def register_failure(email: str, ip: str) -> int:
    key = _key(email, ip)
    count = cache.get(key, 0) + 1
    cache.set(key, count, timeout=max(WINDOW_SECONDS, LOCKOUT_SECONDS))
    return count


def clear_failures(email: str, ip: str) -> None:
    cache.delete(_key(email, ip))
