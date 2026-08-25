"""
Coverage for `publish_theme_version`/`publish_theme_preset` themselves
-- same shape as apps/subscriptions/tests/test_plan_version_isolation.py's
coverage of `publish_plan_version` / apps/notifications/tests/
test_publish_notification_template_command.py: reject writing through
anything but the migrator alias, then verify the upsert semantics via
that same alias (app_user has no write policy on these tables at all).
"""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.themes.models import Theme, ThemePreset, ThemeVersion

pytestmark = pytest.mark.django_db(databases=["default", "migrator"])


def _delete_aurora_version_2() -> None:
    ThemeVersion.objects.using("migrator").filter(theme__code="aurora", version_number=2).delete()


def test_publish_theme_version_rejects_the_default_database_alias():
    with pytest.raises(CommandError, match="migrator"):
        call_command("publish_theme_version", theme_code="aurora")


def test_publish_theme_version_publishes_the_next_incrementing_version():
    call_command("publish_theme_version", database="migrator", theme_code="aurora")
    try:
        theme = Theme.objects.using("migrator").get(code="aurora")
        versions = list(
            ThemeVersion.objects.using("migrator").filter(theme=theme).order_by("version_number")
        )
        assert [v.version_number for v in versions] == [1, 2]
        assert versions[0].is_current is False  # flipped off by the new publish
        assert versions[1].is_current is True
    finally:
        _delete_aurora_version_2()
        ThemeVersion.objects.using("migrator").filter(
            theme__code="aurora", version_number=1
        ).update(is_current=True)


def test_publish_theme_version_no_current_flag_does_not_disturb_the_existing_current():
    call_command("publish_theme_version", database="migrator", theme_code="aurora", no_current=True)
    try:
        theme = Theme.objects.using("migrator").get(code="aurora")
        current = ThemeVersion.objects.using("migrator").get(theme=theme, is_current=True)
        assert current.version_number == 1
    finally:
        _delete_aurora_version_2()


def test_publish_theme_version_rejects_an_unknown_theme_code():
    with pytest.raises(CommandError, match="No Theme"):
        call_command("publish_theme_version", database="migrator", theme_code="does-not-exist")


def test_publish_theme_preset_rejects_an_unknown_theme_version():
    with pytest.raises(CommandError, match="No ThemeVersion"):
        call_command(
            "publish_theme_preset",
            database="migrator",
            theme_code="aurora",
            theme_version=999,
            name="x",
            theme_settings="{}",
        )


def test_publish_theme_preset_rejects_a_version_with_no_registered_settings_contract():
    """A real ThemeVersion can exist with no entry in
    apps.themes.schemas._SETTINGS_SERIALIZERS yet (a deployment step
    genuinely ahead of code registering that version's contract) --
    UnknownThemeContractError, not a validation failure."""
    call_command("publish_theme_version", database="migrator", theme_code="aurora")
    try:
        with pytest.raises(CommandError, match="No settings contract registered"):
            call_command(
                "publish_theme_preset",
                database="migrator",
                theme_code="aurora",
                theme_version=2,
                name="x",
                theme_settings="{}",
            )
    finally:
        _delete_aurora_version_2()
        ThemeVersion.objects.using("migrator").filter(
            theme__code="aurora", version_number=1
        ).update(is_current=True)


def test_publish_theme_preset_rejects_the_default_database_alias():
    with pytest.raises(CommandError, match="migrator"):
        call_command(
            "publish_theme_preset",
            theme_code="aurora",
            theme_version=1,
            name="x",
            theme_settings="{}",
        )


def test_publish_theme_preset_creates_and_upserts_in_place():
    call_command(
        "publish_theme_preset",
        database="migrator",
        theme_code="aurora",
        theme_version=1,
        name="Test Preset",
        theme_settings='{"primary_color": "#000000"}',
    )
    try:
        first = ThemePreset.objects.using("migrator").get(name="Test Preset")
        assert first.default_settings["primary_color"] == "#000000"
        # validated -- unlisted defaults filled in by the settings serializer
        assert first.default_settings["font_choice"] == "inter"

        call_command(
            "publish_theme_preset",
            database="migrator",
            theme_code="aurora",
            theme_version=1,
            name="Test Preset",
            theme_settings='{"primary_color": "#ffffff"}',
        )
        second = ThemePreset.objects.using("migrator").get(name="Test Preset")
        assert second.id == first.id  # same logical row, updated in place
        assert second.default_settings["primary_color"] == "#ffffff"
    finally:
        ThemePreset.objects.using("migrator").filter(name="Test Preset").delete()


def test_publish_theme_preset_rejects_invalid_settings():
    with pytest.raises(CommandError, match="validation"):
        call_command(
            "publish_theme_preset",
            database="migrator",
            theme_code="aurora",
            theme_version=1,
            name="Bad Preset",
            theme_settings='{"primary_color": "not-a-color"}',
        )


def test_publish_theme_preset_rejects_invalid_json():
    with pytest.raises(CommandError, match="JSON"):
        call_command(
            "publish_theme_preset",
            database="migrator",
            theme_code="aurora",
            theme_version=1,
            name="Bad JSON",
            theme_settings="not-json",
        )


def test_publish_theme_preset_default_flag_unsets_the_previous_default():
    call_command(
        "publish_theme_preset",
        database="migrator",
        theme_code="aurora",
        theme_version=1,
        name="New Default",
        theme_settings="{}",
        default=True,
    )
    try:
        old_default = ThemePreset.objects.using("migrator").get(name="Default")
        new_default = ThemePreset.objects.using("migrator").get(name="New Default")
        assert old_default.is_default is False
        assert new_default.is_default is True
    finally:
        ThemePreset.objects.using("migrator").filter(name="New Default").delete()
        ThemePreset.objects.using("migrator").filter(name="Default").update(is_default=True)
