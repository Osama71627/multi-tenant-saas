"""
Phase 12, Theme/Template decision (approved Option B): "no Store may
exist with no deterministic theme state", same invariant Phase 10
established for entitlements -- proven directly here the same way
test_store_creation_atomicity.py proves it for Subscription: an invalid
`theme_preset_id` must roll Store/StoreDomain/StoreMembership back
together, not just leave the theme step failed; a valid explicit choice
must produce a `StoreThemeConfig` pinned to exactly that preset, proving
"selected preset + store details -> create_store(...) -> ... ->
StoreThemeConfig -> commit" is a single atomic operation, never a
frontend-orchestrated multi-write sequence.
"""

from __future__ import annotations

import json

import psycopg
import pytest
from django.db import connections

from apps.accounts.models import PlatformUser, StoreMembership
from apps.core.uuid7 import uuid7
from apps.stores.hooks import PostCreationHookError
from apps.stores.models import Store, StoreDomain
from apps.stores.services import create_store
from apps.tenancy.context import TenantContext, tenant_context
from apps.tenancy.db import apply_tenant_context_to_db, clear_tenant_context_from_db
from apps.themes.models import StoreThemeConfig, ThemePreset

pytestmark = pytest.mark.django_db(databases=["default", "migrator"])


@pytest.fixture
def owner():
    return PlatformUser.objects.create_user(
        email="theme-atomic-owner@example.com", password="correct-h0rse!"  # noqa: S106
    )


def test_an_invalid_theme_preset_id_rolls_back_store_domain_and_membership_together(owner):
    bogus_preset_id = uuid7()

    with pytest.raises(PostCreationHookError):
        create_store(
            owner=owner,
            name="Theme Atomic Co",
            slug="theme-atomic-co",
            theme_preset_id=bogus_preset_id,
        )

    assert not Store.objects.filter(slug="theme-atomic-co").exists()
    assert not StoreDomain.unscoped.filter(hostname__startswith="theme-atomic-co.").exists()
    assert not StoreMembership.unscoped.filter(user=owner).exists()


def test_store_creation_with_no_explicit_preset_provisions_the_default_theme_config(owner):
    store = create_store(owner=owner, name="Theme Default Co", slug="theme-default-co")

    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            config = StoreThemeConfig.objects.get(store=store)
            assert config.preset is not None
            assert config.preset.is_default is True
            assert config.theme_version_id == config.preset.theme_version_id
        finally:
            clear_tenant_context_from_db()


def test_store_creation_with_an_explicit_preset_choice_pins_that_exact_preset(owner):
    default_preset = ThemePreset.objects.get(is_default=True)

    # A second, non-default preset on the same seeded ThemeVersion, so
    # picking it is unambiguously distinguishable from "the default was
    # used anyway". `app_user` has no write policy on ThemePreset at all
    # (approved global-readonly RLS) -- and a `.using("migrator")` ORM
    # write here would sit in ITS OWN uncommitted pytest-django test
    # transaction, invisible to the "default" connection `create_store`
    # actually queries through (the same cross-connection-visibility
    # constraint documented in apps/notifications/tests/test_localization.py).
    # A real committed row via a raw autocommit psycopg connection --
    # same pattern as test_store_creation_atomicity.py's
    # `no_default_trial_plan` fixture -- is the only way to make this
    # preset genuinely visible to `create_store`'s own connection.
    # NOT cleaned up with a matching DELETE afterward, deliberately: this
    # row gets FK-referenced by a `StoreThemeConfig` created on the
    # "default" connection's own (separate, still-open) test transaction.
    # Deleting it here -- via a genuinely different autocommit connection,
    # before that other transaction has rolled back -- would delete a row
    # the still-open transaction references, which Django's teardown
    # discovers as a dangling foreign key the moment it runs its deferred
    # constraint check (`SET CONSTRAINTS ALL IMMEDIATE`, just before the
    # rollback that would have made this moot). Left in place, it's one
    # harmless extra row in the isolated test database only (never the
    # real dev DB -- `DATABASES["migrator"]["TEST"]` is its own separate
    # database, config/settings/test.py), the same category of tradeoff
    # `test_concurrency.py`-style tests already accept.
    explicit_preset_id = uuid7()
    migrator_params = connections["migrator"].get_connection_params()
    conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        conn.execute(
            "INSERT INTO themes_themepreset "
            "(id, created_at, updated_at, name, default_settings, preview_image_url, "
            "is_active, is_default, theme_version_id) "
            "VALUES (%s, now(), now(), %s, %s::jsonb, '', true, false, %s)",
            [
                str(explicit_preset_id),
                "Explicit Choice",
                json.dumps(default_preset.default_settings),
                str(default_preset.theme_version_id),
            ],
        )
    finally:
        conn.close()

    store = create_store(
        owner=owner,
        name="Theme Explicit Co",
        slug="theme-explicit-co",
        theme_preset_id=explicit_preset_id,
    )

    with tenant_context(TenantContext(store_id=store.id)):
        apply_tenant_context_to_db(store.id)
        try:
            config = StoreThemeConfig.objects.get(store=store)
            assert config.preset_id == explicit_preset_id
            assert config.preset_id != default_preset.id
            assert config.theme_version_id == default_preset.theme_version_id
            assert config.settings == default_preset.default_settings
        finally:
            clear_tenant_context_from_db()
