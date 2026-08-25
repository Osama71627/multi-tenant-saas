"""
Seeds exactly one platform-global default Theme (+ its current
ThemeVersion + one default ThemePreset). Required precondition for
`apps.stores.services.create_store` to succeed AT ALL (approved
Theme/Template decision: every Store gets a `StoreThemeConfig`
provisioned atomically at creation, via
`apps.themes.services.get_default_theme_preset` / `apps.stores.hooks`).
Runs automatically as part of `migrate` in every environment -- same
discipline as `apps/subscriptions/migrations/0002_seed_default_trial_plan.py`.

Uses the migration's own historical model state (`apps.get_model`), not
a direct import of `apps.themes.models` -- standard Django data-
migration practice.

`default_settings` here is a hand-verified match for
`apps.themes.schemas.AuroraV1SettingsSerializer` -- migrations run
outside the app registry the settings-serializer registry depends on
cleanly resolving, so this is intentionally NOT re-validated through
that serializer at seed time (mirrors how Phase 11's template seed
migration doesn't re-run `apps.notifications.rendering` either).
"""

from __future__ import annotations

from django.db import migrations

_THEME_CODE = "aurora"

_DEFAULT_SETTINGS = {
    "primary_color": "#111827",
    "secondary_color": "#6B7280",
    "accent_color": "#2563EB",
    "font_choice": "inter",
    "hero_headline": "Welcome to our store",
    "hero_subheadline": "Quality products, delivered fast.",
    "homepage_sections": ["hero", "featured_products", "categories"],
    "nav_order": ["shop", "about", "contact"],
}


def _seed(apps, schema_editor):
    # Explicit `using=schema_editor.connection.alias` throughout -- see
    # apps/subscriptions/migrations/0002_seed_default_trial_plan.py's
    # docstring for exactly why RunPython's ORM calls need this.
    db = schema_editor.connection.alias
    Theme = apps.get_model("themes", "Theme")
    ThemeVersion = apps.get_model("themes", "ThemeVersion")
    ThemePreset = apps.get_model("themes", "ThemePreset")

    theme = Theme.objects.using(db).create(code=_THEME_CODE, name="Aurora", is_active=True)
    version = ThemeVersion.objects.using(db).create(theme=theme, version_number=1, is_current=True)
    ThemePreset.objects.using(db).create(
        theme_version=version,
        name="Default",
        default_settings=_DEFAULT_SETTINGS,
        preview_image_url="",
        is_active=True,
        is_default=True,
    )


def _unseed(apps, schema_editor):
    db = schema_editor.connection.alias
    Theme = apps.get_model("themes", "Theme")
    Theme.objects.using(db).filter(code=_THEME_CODE).delete()  # cascades version/preset


class Migration(migrations.Migration):

    dependencies = [
        ("themes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(_seed, _unseed),
    ]
