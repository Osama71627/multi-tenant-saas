"""
The permission catalog and role->permission defaults for the RBAC system
(docs/ARCHITECTURE.md section 4 "Store Staff"). Deliberately small right
now: no domain app (catalog/orders/payments/...) exists yet to define
permissions over, so the catalog only covers what's real today (store-
level identity/settings). Each domain phase adds its own keys here (or a
sibling module) plus updates `ROLE_BASE_PERMISSIONS` -- that's the whole
extension mechanism, no re-architecture needed.

`"*"` is a wildcard meaning "every current and future permission" --
granted only to `Role.OWNER`, matching "Store Owner can manage everything
about their store" from the original spec.
"""

from __future__ import annotations


class Permissions:
    STORE_VIEW = "store.view"
    STORE_SETTINGS_WRITE = "store.settings.write"
    STORE_STAFF_MANAGE = "store.staff.manage"
    STORE_BILLING_MANAGE = "store.billing.manage"


ROLE_BASE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": frozenset({"*"}),
    "admin": frozenset(
        {Permissions.STORE_VIEW, Permissions.STORE_SETTINGS_WRITE, Permissions.STORE_STAFF_MANAGE}
    ),
    "manager": frozenset({Permissions.STORE_VIEW, Permissions.STORE_SETTINGS_WRITE}),
    "staff": frozenset({Permissions.STORE_VIEW}),
    "viewer": frozenset({Permissions.STORE_VIEW}),
}


def resolve_permissions(*, role: str, status: str, extra_permissions: list[str]) -> frozenset[str]:
    """Pure function -- no DB access -- so it's trivially unit-testable."""
    if status != "active":
        return frozenset()
    return ROLE_BASE_PERMISSIONS.get(role, frozenset()) | frozenset(extra_permissions)


def has_permission(
    *, role: str, status: str, extra_permissions: list[str], permission: str
) -> bool:
    granted = resolve_permissions(role=role, status=status, extra_permissions=extra_permissions)
    return "*" in granted or permission in granted
