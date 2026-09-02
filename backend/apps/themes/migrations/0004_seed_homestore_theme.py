"""
A fifth theme -- HomeStore -- requested directly by the user, who
brought a real, complete, previously-built storefront design (a
separate Django project, github.com/Osama71627/Online_shop) to use as
the source design: sticky glassmorphism header, hero banner, trust-
badge strip, image categories, featured products, an on-sale grid,
newsletter -- translated into this project's own React/Next.js theme-
package architecture (`@saas/theme-homestore`), same settings CONTRACT
as every other theme (this migration only adds a new (code, preset)
pair, not a new contract -- see apps.themes.schemas's own comment on
why the contract is shared while the RENDERING differs per theme).

Same pattern as 0003_theme_category_and_new_themes.py in every other
respect (Theme -> ThemeVersion -> ThemePreset, is_default=False --
Aurora keeps the sole default).
"""

from __future__ import annotations

from django.db import migrations

_HOMESTORE = {
    "code": "homestore",
    "name": "HomeStore",
    "category": "Home & Kitchen",
    "preset_name": "HomeStore Default",
    "default_settings": {
        "primary_color": "#171717",
        "secondary_color": "#2563EB",
        "accent_color": "#F59E0B",
        "font_choice": "inter",
        "hero_headline": "Elevate Everyday Living",
        "hero_subheadline": "Premium home essentials, thoughtfully curated.",
        "homepage_sections": ["hero", "categories", "featured_products", "newsletter"],
        "nav_order": ["shop", "about", "contact"],
    },
}


def _seed(apps, schema_editor):
    db = schema_editor.connection.alias
    Theme = apps.get_model("themes", "Theme")
    ThemeVersion = apps.get_model("themes", "ThemeVersion")
    ThemePreset = apps.get_model("themes", "ThemePreset")

    theme = Theme.objects.using(db).create(
        code=_HOMESTORE["code"],
        name=_HOMESTORE["name"],
        category=_HOMESTORE["category"],
        is_active=True,
    )
    version = ThemeVersion.objects.using(db).create(theme=theme, version_number=1, is_current=True)
    ThemePreset.objects.using(db).create(
        theme_version=version,
        name=_HOMESTORE["preset_name"],
        default_settings=_HOMESTORE["default_settings"],
        preview_image_url="",
        is_active=True,
        is_default=False,
    )


def _unseed(apps, schema_editor):
    db = schema_editor.connection.alias
    Theme = apps.get_model("themes", "Theme")
    Theme.objects.using(db).filter(code=_HOMESTORE["code"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("themes", "0003_theme_category_and_new_themes"),
    ]

    operations = [
        migrations.RunPython(_seed, _unseed),
    ]
