"""
Approval section 3: a guard proving the `platform` DB alias
(`app_platform_admin`) is never referenced outside `apps.platform_admin`.

This is a literal source-text scan, deliberately NOT relying on
import-linter for this specific claim: import-linter proves the Python
IMPORT graph (see the "nothing below platform_admin may import it"
contract in pyproject.toml), which is a real, valuable, but DIFFERENT
guarantee -- it does not, and cannot, prove that no OTHER app's code
contains the literal string `.using("platform")` or otherwise opens a
connection to that alias by some other means (a raw `connections["platform"]`
lookup, a dynamically-built string, etc.). This test closes that specific
gap for the two concrete ways this codebase actually names the alias/role,
and documents exactly what it does and does not prove.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_APPS_DIR = Path(__file__).resolve().parents[2]
_ALLOWED_PREFIX = _APPS_DIR / "platform_admin"
_NEEDLES = (
    '.using("platform")',
    ".using('platform')",
    'connections["platform"]',
    "connections['platform']",
)
# apps/tenancy/rls.py's `platform_admin_only_policy_sql` docstring names
# the role to explain the RLS shape it generates -- documentation, not a
# connection/alias reference. apps.tenancy is the allowed, foundational
# direction (every domain app depends on it), and this is the one
# expected, reviewed exception -- same shape as the documented
# `ignore_imports` exceptions in pyproject.toml's import-linter contracts.
_ROLE_NAME_ALLOWLIST = {_APPS_DIR / "tenancy" / "rls.py"}


def _iter_source_files():
    for path in _APPS_DIR.rglob("*.py"):
        if _ALLOWED_PREFIX in path.parents:
            continue
        if "__pycache__" in path.parts:
            continue
        yield path


def test_platform_alias_never_referenced_outside_platform_admin():
    offenders = []
    for path in _iter_source_files():
        text = path.read_text(encoding="utf-8")
        for needle in _NEEDLES:
            if needle in text:
                offenders.append((str(path.relative_to(_APPS_DIR.parent)), needle))

    assert not offenders, (
        "Found references to the privileged 'platform' DB alias outside "
        f"apps.platform_admin: {offenders}"
    )


def test_app_platform_admin_role_name_never_referenced_outside_platform_admin():
    """Same guard for the raw role name, in case future code opens the
    alias by role name (e.g. a raw psycopg connection) rather than
    Django's `.using("platform")`."""
    offenders = []
    for path in _iter_source_files():
        if path in _ROLE_NAME_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        if "app_platform_admin" in text:
            offenders.append(str(path.relative_to(_APPS_DIR.parent)))

    assert (
        not offenders
    ), f"Found references to 'app_platform_admin' outside apps.platform_admin: {offenders}"


@pytest.mark.django_db
def test_sanity_the_scan_actually_finds_the_alias_inside_platform_admin():
    """Guards the guard: if this ever finds ZERO matches even inside
    apps.platform_admin, the scan itself is broken (e.g. a bad path),
    not proof that nothing needs guarding."""
    matches = 0
    for path in _APPS_DIR.rglob("*.py"):
        if _ALLOWED_PREFIX not in path.parents:
            continue
        text = path.read_text(encoding="utf-8")
        if any(needle in text for needle in _NEEDLES):
            matches += 1
    assert (
        matches > 0
    ), "Expected at least one legitimate '.using(\"platform\")' use inside apps.platform_admin."
