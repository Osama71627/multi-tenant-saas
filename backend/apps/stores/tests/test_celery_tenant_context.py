"""
Proves docs/DECISIONS.md governance point 1's Celery requirement: tasks
that touch tenant-owned data cannot run without an explicit store_id, and
running one for store A can never see/touch store B's data -- even though
Celery worker processes are long-lived and reused across many stores'
jobs. `CELERY_TASK_ALWAYS_EAGER=True` in config/settings/test.py makes
`.apply_async()` run synchronously in-process, which is what makes these
assertions possible without a running broker/worker.
"""

import pytest
from celery import shared_task
from django.db import transaction

from apps.stores.models import Store, StoreDomain
from apps.tenancy.celery import PlatformTask, TenantTask, dispatch_for_store
from apps.tenancy.context import TenantContext, get_current_store_id, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db

pytestmark = pytest.mark.django_db

_captured_store_ids: list = []


@shared_task(base=TenantTask, name="tenancy.tests.record_current_store_id")
def _record_current_store_id():
    _captured_store_ids.append(get_current_store_id())


@shared_task(base=TenantTask, name="tenancy.tests.count_visible_domains")
def _count_visible_domains():
    return StoreDomain.objects.count()


def _make_store(slug: str) -> Store:
    with tenant_context(None):
        apply_tenant_context_to_db(None)
        try:
            return Store.objects.create(name=slug, slug=slug)
        finally:
            clear_tenant_context_from_db()


def _make_domain(store: Store, hostname: str) -> StoreDomain:
    with tenant_context(TenantContext(store_id=store.id)):
        with transaction.atomic(using="default"):
            apply_tenant_context_to_db(store.id)
            try:
                return StoreDomain.objects.create(store=store, hostname=hostname)
            finally:
                clear_tenant_context_from_db()


@pytest.fixture(autouse=True)
def _reset_capture():
    _captured_store_ids.clear()
    yield
    _captured_store_ids.clear()


def test_dispatching_without_store_id_is_rejected():
    with pytest.raises(TypeError, match="TenantTask"):
        _record_current_store_id.apply_async()


def test_dispatching_via_delay_without_store_id_is_also_rejected():
    with pytest.raises(TypeError):
        _record_current_store_id.delay()


def test_dispatch_for_store_sets_the_context_inside_the_task():
    store = _make_store("celery-ctx-store")
    dispatch_for_store(_record_current_store_id, store.id)
    assert _captured_store_ids == [store.id]


def test_context_does_not_leak_to_the_next_task_on_the_same_worker():
    store_a = _make_store("celery-leak-a")
    store_b = _make_store("celery-leak-b")

    dispatch_for_store(_record_current_store_id, store_a.id)
    dispatch_for_store(_record_current_store_id, store_b.id)

    assert _captured_store_ids == [store_a.id, store_b.id]
    # And after both tasks finish, no tenant context should remain "stuck".
    assert get_current_store_id() is None


def test_task_for_store_a_cannot_see_store_bs_rows():
    store_a = _make_store("celery-scope-a")
    store_b = _make_store("celery-scope-b")
    _make_domain(store_a, "celery-scope-a.example.com")
    _make_domain(store_b, "celery-scope-b.example.com")
    _make_domain(store_b, "celery-scope-b-2.example.com")

    result = dispatch_for_store(_count_visible_domains, store_a.id)
    assert result.get() == 1, "task saw more than just store A's own domain(s)"


class _PlainPlatformTask(PlatformTask):
    name = "tenancy.tests.plain_platform_task"

    def run(self):
        return get_current_store_id()


def test_platform_task_has_no_ambient_tenant():
    task = _PlainPlatformTask()
    assert task.run() is None
