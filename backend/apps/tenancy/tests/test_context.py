import uuid

from apps.tenancy.context import (
    TenantContext,
    get_current_store_id,
    get_current_tenant,
    reset_current_tenant,
    set_current_tenant,
    tenant_context,
)


def test_defaults_to_no_tenant():
    assert get_current_tenant() is None
    assert get_current_store_id() is None


def test_set_and_reset_round_trips():
    store_id = uuid.uuid4()
    token = set_current_tenant(TenantContext(store_id=store_id))
    try:
        assert get_current_store_id() == store_id
    finally:
        reset_current_tenant(token)
    assert get_current_tenant() is None


def test_context_manager_clears_on_normal_exit():
    store_id = uuid.uuid4()
    with tenant_context(TenantContext(store_id=store_id)):
        assert get_current_store_id() == store_id
    assert get_current_tenant() is None


def test_context_manager_clears_even_on_exception():
    store_id = uuid.uuid4()
    try:
        with tenant_context(TenantContext(store_id=store_id)):
            assert get_current_store_id() == store_id
            raise ValueError("boom")
    except ValueError:
        pass
    assert get_current_tenant() is None, "tenant context leaked past an exception"


def test_nested_contexts_restore_the_outer_one():
    outer = uuid.uuid4()
    inner = uuid.uuid4()
    with tenant_context(TenantContext(store_id=outer)):
        assert get_current_store_id() == outer
        with tenant_context(TenantContext(store_id=inner)):
            assert get_current_store_id() == inner
        assert get_current_store_id() == outer, "inner context leaked into outer scope"
    assert get_current_tenant() is None
