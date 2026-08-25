"""
Test-support registry for the generic tenant-isolation test suite
(backend/tests/test_tenant_isolation.py).

Deliberately lives in `apps.tenancy` (not `apps.tenancy.tests`) and has NO
imports of any domain app -- the import-linter contract in pyproject.toml
forbids `apps.tenancy` from depending on `apps.stores`/`apps.catalog`/etc.,
and that boundary should hold for this file too, even though it's test
infrastructure. Domain apps import *this* module and register themselves
into it (the allowed direction), e.g. apps/stores/tests/isolation_factories.py.

Why a registry instead of pure reflection/auto-instantiation: Django models
often have required fields, unique constraints, and validation the test
suite can't safely guess generically (e.g. StoreDomain.hostname must be
globally unique). A registry keeps model construction correct and
explicit while still making the coverage check ("did anyone forget to
register their new tenant-owned model?") fully automatic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class IsolationSpec:
    factory: Callable[[Any, str], Any]
    select_is_open: bool = False
    """
    True only for the rare, deliberately-documented table (e.g.
    StoreDomain) whose RLS SELECT policy is `USING (true)` on purpose --
    see its migration for why. For every ordinary TenantOwnedModel this
    must stay False, which is also the default: a new model that forgets
    to think about this gets the strict (and correct) assumption.
    """


_registry: dict[type, IsolationSpec] = {}


def register(model: type, *, select_is_open: bool = False):
    """
    Decorator: `@register(StoreDomain, select_is_open=True)` on a
    `factory(store, suffix) -> instance` function. The factory MUST create
    the row with `store=store` (i.e. via `Model.objects.create(store=store,
    ...)` while the tenant context is set to that store) -- the generic
    isolation tests reuse the same factory, with a *different* store
    passed in, to prove that RLS also rejects writing a row for one store
    while the request/task context is another (the "attacker edits
    store_id in the request body" scenario).
    """

    def decorator(factory: Callable[[Any, str], Any]):
        _registry[model] = IsolationSpec(factory=factory, select_is_open=select_is_open)
        return factory

    return decorator


def all_registered() -> dict[type, IsolationSpec]:
    return dict(_registry)
