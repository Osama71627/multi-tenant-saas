from __future__ import annotations

import json
import uuid

import psycopg
import pytest
from django.db import connections

from apps.accounts.models import PlatformUser
from apps.core.uuid7 import uuid7
from apps.stores.services import create_store
from apps.themes import services
from apps.themes.models import ThemePreset

pytestmark = pytest.mark.django_db(databases=["default", "migrator"])


@pytest.fixture
def owner():
    return PlatformUser.objects.create_user(
        email="provisioning-owner@example.com", password="correct-h0rse!"  # noqa: S106
    )


def test_get_default_theme_preset_returns_the_seeded_default():
    preset = services.get_default_theme_preset()
    assert preset.is_default is True
    assert preset.is_active is True


def test_resolve_theme_preset_with_none_falls_back_to_default():
    resolved = services.resolve_theme_preset(theme_preset_id=None)
    assert resolved.is_default is True


def test_resolve_theme_preset_rejects_an_unknown_id():
    with pytest.raises(services.ThemePresetNotFoundError):
        services.resolve_theme_preset(theme_preset_id=uuid.uuid4())


def test_resolve_theme_preset_rejects_an_inactive_preset():
    default_preset = ThemePreset.objects.get(is_default=True)
    # Real committed row via autocommit -- the same cross-connection-
    # visibility constraint as apps/stores/tests/test_store_theme_atomicity.py
    # applies here too: `resolve_theme_preset` reads via the "default"
    # alias, so an insert on "migrator" only matters if genuinely committed.
    inactive_preset_id = uuid7()
    migrator_params = connections["migrator"].get_connection_params()
    conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        conn.execute(
            "INSERT INTO themes_themepreset "
            "(id, created_at, updated_at, name, default_settings, preview_image_url, "
            "is_active, is_default, theme_version_id) "
            "VALUES (%s, now(), now(), 'Inactive', %s::jsonb, '', false, false, %s)",
            [
                str(inactive_preset_id),
                json.dumps(default_preset.default_settings),
                str(default_preset.theme_version_id),
            ],
        )
    finally:
        conn.close()

    with pytest.raises(services.ThemePresetNotFoundError):
        services.resolve_theme_preset(theme_preset_id=inactive_preset_id)


def test_no_default_theme_preset_raises_a_deployment_error(owner):
    """Temporarily un-marks the seeded default preset, then restores it --
    via the migrator connection (app_user cannot write to ThemePreset at
    all, approved global-readonly RLS). Mirrors
    apps/stores/tests/test_store_creation_atomicity.py's
    `no_default_trial_plan` fixture exactly."""
    migrator_params = connections["migrator"].get_connection_params()
    conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        conn.execute("UPDATE themes_themepreset SET is_default = false WHERE is_default = true")
        with pytest.raises(services.NoDefaultThemePresetError):
            create_store(owner=owner, name="No Default Theme Co", slug="no-default-theme-co")
    finally:
        conn.execute(
            "UPDATE themes_themepreset SET is_default = true "
            "WHERE name = 'Default' AND is_default = false"
        )
        conn.close()
