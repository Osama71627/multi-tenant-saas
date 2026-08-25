import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import PlatformUser, StoreMembership
from apps.accounts.permissions_catalog import Permissions, has_permission
from apps.stores.models import Store
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

pytestmark = pytest.mark.django_db


@pytest.fixture
def store():
    with tenant_context(None):
        apply_tenant_context_to_db(None)
        try:
            return Store.objects.create(name="membership-test-store", slug="membership-test-store")
        finally:
            clear_tenant_context_from_db()


@pytest.fixture
def owner_user():
    return PlatformUser.objects.create_user(email="member-owner@example.com", password="x12345678!")


def _create_membership(store, user, **kwargs):
    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            return StoreMembership.objects.create(store=store, user=user, **kwargs)
        finally:
            clear_tenant_context_from_db()


def test_a_user_can_only_have_one_membership_per_store(store, owner_user):
    _create_membership(store, owner_user, role=StoreMembership.Role.OWNER)

    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            with pytest.raises(IntegrityError), transaction.atomic(using="default"):
                StoreMembership.objects.create(
                    store=store, user=owner_user, role=StoreMembership.Role.STAFF
                )
        finally:
            clear_tenant_context_from_db()


def test_membership_permissions_reflect_role_and_status(store, owner_user):
    membership = _create_membership(store, owner_user, role=StoreMembership.Role.STAFF)
    assert has_permission(
        role=membership.role,
        status=membership.status,
        extra_permissions=membership.extra_permissions,
        permission=Permissions.STORE_VIEW,
    )
    assert not has_permission(
        role=membership.role,
        status=membership.status,
        extra_permissions=membership.extra_permissions,
        permission=Permissions.STORE_STAFF_MANAGE,
    )


def test_removed_membership_grants_no_permissions_even_for_owner(store, owner_user):
    membership = _create_membership(
        store, owner_user, role=StoreMembership.Role.OWNER, status=StoreMembership.Status.REMOVED
    )
    assert not has_permission(
        role=membership.role,
        status=membership.status,
        extra_permissions=membership.extra_permissions,
        permission=Permissions.STORE_VIEW,
    )


def test_extra_permissions_grant_a_staff_member_one_specific_extra_capability(store, owner_user):
    membership = _create_membership(
        store,
        owner_user,
        role=StoreMembership.Role.STAFF,
        extra_permissions=[Permissions.STORE_SETTINGS_WRITE],
    )
    assert has_permission(
        role=membership.role,
        status=membership.status,
        extra_permissions=membership.extra_permissions,
        permission=Permissions.STORE_SETTINGS_WRITE,
    )
    assert not has_permission(
        role=membership.role,
        status=membership.status,
        extra_permissions=membership.extra_permissions,
        permission=Permissions.STORE_STAFF_MANAGE,
    )
