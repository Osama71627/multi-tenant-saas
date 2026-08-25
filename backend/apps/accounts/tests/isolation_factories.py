"""
Registers apps.accounts' TenantOwnedModel subclass (StoreMembership) with
the generic isolation test suite (backend/tests/test_tenant_isolation.py).
See apps/stores/tests/isolation_factories.py for the pattern this follows.
"""

from apps.accounts.models import PlatformUser, StoreMembership
from apps.tenancy.testing import register


@register(StoreMembership)
def _make_store_membership(store, suffix: str) -> StoreMembership:
    user = PlatformUser.objects.create_user(
        email=f"isolation-{store.slug}-{suffix}@example.com",
        password="not-used-in-these-tests-12345",  # noqa: S106
    )
    return StoreMembership.objects.create(store=store, user=user, role=StoreMembership.Role.STAFF)
