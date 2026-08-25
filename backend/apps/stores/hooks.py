"""
Explicit "run right after a Store's core rows exist" extension point.

`apps.stores.services.create_store` is the ONLY place a `Store` comes
into existence, and several higher layers legitimately need to react to
that atomically (Phase 10: `apps.subscriptions` provisions a trial
Subscription in the SAME transaction -- approved architecture decision
12, "no Store may exist with no deterministic entitlement state"). Since
the dependency direction in this project is always "higher layer depends
on lower layer, never the reverse" (docs/ARCHITECTURE.md section 3), and
apps.subscriptions genuinely needs `Store`/`Store.Status` at runtime
(its lifecycle sweep scans `Store.objects`), it cannot sit BELOW
apps.stores -- so `create_store` cannot import it directly without
inverting that direction.

This registry breaks the tie the same way
`apps.subscriptions.entitlements.register_live_counter` already does for
apps.catalog: the LOWER layer (this module, owned by apps.stores) defines
the extension point; the HIGHER layer registers a callable into it from
its own `AppConfig.ready()` (see apps/subscriptions/apps.py). apps.stores
itself never imports apps.subscriptions.

Hooks run INSIDE `create_store`'s existing `transaction.atomic()` block,
with tenant context already set to the new store's id -- a hook that
raises rolls back Store/StoreDomain/StoreMembership right along with it.

`run_post_creation_hooks` accepts arbitrary `**extra_context` and forwards
it verbatim to every registered hook (Phase 12, Theme/Template decision:
`apps.themes` needs the caller-selected `theme_preset_id`, which
`apps.subscriptions`'s trial-provisioning hook doesn't care about at all).
This module stays completely ignorant of what any given key MEANS --
`apps.stores` must not gain theme-shaped (or any other higher-layer)
knowledge just to pass a value through. Each hook's own signature picks
out only the keys it needs and accepts `**kwargs` for the rest, so
`apps.stores` can add future extra-context keys for some other future
higher-layer app without ever touching hooks that don't care.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.stores.models import Store


class PostCreationHookError(Exception):
    """
    Raised by a registered post-creation hook to reject the WHOLE Store
    creation with a client-facing reason (Phase 12: `apps.themes` raises
    this for an invalid/inactive `theme_preset_id`) -- same "lower layer
    owns the generic extension point" shape as `WriteBlockedError` below.
    `apps.stores.views.StoreListCreateView` catches this ONE generic type
    without ever importing whichever higher-layer app actually raised it;
    `create_store`'s transaction has already rolled back by the time this
    propagates out, so there is no partially-provisioned Store to clean up.
    """


_post_creation_hooks: list[Callable[..., None]] = []


def register_post_creation_hook(hook: Callable[..., None]) -> None:
    """`hook(store, **extra_context)` -- idempotent registration is the
    caller's responsibility (matches `entitlements.register_live_counter`)
    -- safe to call more than once under the dev autoreloader since it
    just overwrites via a dict there; here, `AppConfig.ready()` runs once
    per process in practice, and a duplicate hook would only double-run
    harmless idempotent work, never corrupt state, since e.g.
    `provision_trial_subscription`/`provision_store_theme` are not
    re-entrant-safe by design (one row per store, enforced by a DB
    constraint) -- a second registration would surface immediately as an
    IntegrityError in tests, not silently.
    """
    _post_creation_hooks.append(hook)


def run_post_creation_hooks(*, store: Store, **extra_context: object) -> None:
    for hook in _post_creation_hooks:
        hook(store, **extra_context)


class WriteBlockedError(Exception):
    """
    Raised by a registered write-gate to block a dashboard write (any
    non-safe-method request through `apps.stores.mixins.StoreScopedAPIView`).
    apps.stores translates this into an HTTP 402 without ever needing to
    know WHICH higher-layer app raised it or why -- Phase 10 registers a
    gate here (`apps/subscriptions/apps.py`) that wraps
    `apps.subscriptions.entitlements.StoreNotPurchasableError`, same
    "lower layer owns the generic extension point" shape as
    `register_post_creation_hook` above.
    """


_write_gates: list[Callable[[Store], None]] = []


def register_write_gate(gate: Callable[[Store], None]) -> None:
    """`gate(store)` must raise `WriteBlockedError` to block, or return
    normally to allow."""
    _write_gates.append(gate)


def check_write_gates(*, store: Store) -> None:
    for gate in _write_gates:
        gate(store)
