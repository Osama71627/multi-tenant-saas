"""
Required proof, Theme/Template decision (approved Option B): RLS is the
actual write boundary on the platform-global Theme/ThemeVersion/
ThemePreset tables, not just the ABSENCE of an INSERT/UPDATE/DELETE
policy on paper, and NOT the PostgreSQL table-level GRANT (which
`app_user` genuinely holds -- apps/tenancy/privileges.py's post_migrate
hook grants all four verbs on ALL tables). Same shape as Phase 10's
test_plan_rls.py / Phase 11's test_template_rls.py.
"""

from __future__ import annotations

import pytest
from django.db import Error as DjangoDatabaseError
from django.db import connection, transaction

from apps.themes.models import Theme, ThemePreset, ThemeVersion

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded_theme() -> Theme:
    return Theme.objects.get(code="aurora")


@pytest.fixture
def seeded_preset() -> ThemePreset:
    return ThemePreset.objects.get(is_default=True)


def test_app_user_can_select_themes_versions_and_presets(seeded_theme, seeded_preset):
    assert Theme.objects.filter(id=seeded_theme.id).exists()
    assert ThemeVersion.objects.filter(theme=seeded_theme).exists()
    assert ThemePreset.objects.filter(id=seeded_preset.id).exists()


def test_app_user_cannot_insert_a_theme():
    with pytest.raises(DjangoDatabaseError):
        with transaction.atomic(using="default"):
            Theme.objects.create(code="attempted-insert", name="Attempted Insert")


def test_app_user_cannot_insert_a_theme_preset(seeded_theme):
    theme_version = ThemeVersion.objects.get(theme=seeded_theme, is_current=True)
    with pytest.raises(DjangoDatabaseError):
        with transaction.atomic(using="default"):
            ThemePreset.objects.create(theme_version=theme_version, name="Attempted Insert")


def test_app_user_cannot_update_a_theme_preset(seeded_preset):
    """UPDATE (unlike INSERT) doesn't raise under RLS -- the row is
    simply invisible to the command, so it matches zero rows. See
    apps/subscriptions/tests/test_plan_rls.py for the full explanation."""
    affected = ThemePreset.objects.filter(id=seeded_preset.id).update(name="Hacked")
    assert affected == 0

    seeded_preset.refresh_from_db()
    assert seeded_preset.name != "Hacked"


def test_app_user_cannot_delete_a_theme_preset(seeded_preset):
    deleted_count, _ = ThemePreset.objects.filter(id=seeded_preset.id).delete()
    assert deleted_count == 0
    assert ThemePreset.objects.filter(id=seeded_preset.id).exists()


def test_rls_is_enabled_on_all_theme_tables():
    with connection.cursor() as cursor:
        for table_name in ["themes_theme", "themes_themeversion", "themes_themepreset"]:
            cursor.execute("SELECT relrowsecurity FROM pg_class WHERE relname = %s", [table_name])
            (enabled,) = cursor.fetchone()
            assert enabled is True, table_name


def test_app_user_has_table_level_write_grant_but_rls_still_blocks(seeded_theme):
    with connection.cursor() as cursor:
        cursor.execute("SELECT has_table_privilege('app_user', 'themes_theme', 'INSERT')")
        (has_insert_grant,) = cursor.fetchone()
    assert has_insert_grant is True  # the blanket table-level GRANT genuinely exists

    with pytest.raises(DjangoDatabaseError):
        with transaction.atomic(using="default"):
            Theme.objects.create(code="grant-vs-rls", name="Grant vs RLS")
