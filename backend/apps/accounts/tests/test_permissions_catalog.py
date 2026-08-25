"""Pure unit tests -- no DB needed, resolve_permissions/has_permission are plain functions."""

from apps.accounts.permissions_catalog import Permissions, has_permission, resolve_permissions


def test_owner_has_wildcard():
    perms = resolve_permissions(role="owner", status="active", extra_permissions=[])
    assert "*" in perms
    assert has_permission(
        role="owner", status="active", extra_permissions=[], permission="anything.at.all"
    )


def test_viewer_only_has_store_view():
    perms = resolve_permissions(role="viewer", status="active", extra_permissions=[])
    assert perms == {Permissions.STORE_VIEW}


def test_inactive_membership_has_no_permissions_regardless_of_role():
    for status in ("invited", "removed"):
        perms = resolve_permissions(role="owner", status=status, extra_permissions=[])
        assert perms == frozenset()
        assert not has_permission(
            role="owner", status=status, extra_permissions=[], permission=Permissions.STORE_VIEW
        )


def test_extra_permissions_are_additive_to_the_role_base_set():
    perms = resolve_permissions(
        role="staff", status="active", extra_permissions=[Permissions.STORE_SETTINGS_WRITE]
    )
    assert perms == {Permissions.STORE_VIEW, Permissions.STORE_SETTINGS_WRITE}


def test_unknown_role_grants_nothing_by_default():
    perms = resolve_permissions(role="not-a-real-role", status="active", extra_permissions=[])
    assert perms == frozenset()
