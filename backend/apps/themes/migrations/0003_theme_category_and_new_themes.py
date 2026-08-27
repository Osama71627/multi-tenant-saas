"""
Phase B ("product vision reset" -- theme marketplace) additions:

1. `Theme.category` -- a plain, human-readable label ("Fashion &
   Apparel", "Electronics", etc.) for the public marketplace card. Not
   a separate model: today it's a 1:1 label per theme, and a full
   Category taxonomy has no product requirement behind it yet (mirrors
   this project's own "don't invent unnecessary structure" discipline
   -- see apps/subscriptions' Plan/PlanVersion for the same restraint).
2. Three new, genuinely distinct themes -- Fashion, Electronics,
   Luxury -- each with its own real frontend component package
   (`@saas/theme-fashion`/`-electronics`/`-luxury`), not a preset
   variation of Aurora. `default_settings` here is hand-verified
   against `apps.themes.schemas`'s shared settings contract (see that
   module's own comment on why the CONTRACT is shared across themes
   while the RENDERING differs) -- same "not re-validated through the
   live serializer at migration time" discipline as
   0002_seed_default_theme.py, for the identical reason (migrations
   run outside the app registry that registry depends on).

Aurora keeps `is_default=True` on its preset -- existing stores and the
current onboarding wizard are untouched by this migration.
"""

from __future__ import annotations

from django.db import migrations, models

_AURORA_CATEGORY = "General Store"

_NEW_THEMES = [
    {
        "code": "fashion",
        "name": "Fashion",
        "category": "Fashion & Apparel",
        "preset_name": "Fashion Default",
        "default_settings": {
            "primary_color": "#1A1A1A",
            "secondary_color": "#C9A987",
            "accent_color": "#E8B4B8",
            "font_choice": "inter",
            "hero_headline": "The New Season Edit",
            "hero_subheadline": "Considered pieces, made to last.",
            "homepage_sections": ["hero", "featured_products", "categories", "newsletter"],
            "nav_order": ["shop", "about", "contact"],
        },
    },
    {
        "code": "electronics",
        "name": "Electronics",
        "category": "Electronics",
        "preset_name": "Electronics Default",
        "default_settings": {
            "primary_color": "#0F172A",
            "secondary_color": "#1D4ED8",
            "accent_color": "#F59E0B",
            "font_choice": "inter",
            "hero_headline": "Tech That Works As Hard As You Do",
            "hero_subheadline": "Top deals on the gear you actually need.",
            "homepage_sections": ["hero", "featured_products", "categories", "newsletter"],
            "nav_order": ["shop", "about", "contact"],
        },
    },
    {
        "code": "luxury",
        "name": "Luxury",
        "category": "Luxury & Lifestyle",
        "preset_name": "Luxury Default",
        "default_settings": {
            "primary_color": "#111111",
            "secondary_color": "#B8A98A",
            "accent_color": "#B8A98A",
            "font_choice": "inter",
            "hero_headline": "Exceptional, By Design",
            "hero_subheadline": "A curated selection for the discerning.",
            "homepage_sections": ["hero", "featured_products", "categories", "newsletter"],
            "nav_order": ["shop", "about", "contact"],
        },
    },
]


def _seed(apps, schema_editor):
    db = schema_editor.connection.alias
    Theme = apps.get_model("themes", "Theme")
    ThemeVersion = apps.get_model("themes", "ThemeVersion")
    ThemePreset = apps.get_model("themes", "ThemePreset")

    Theme.objects.using(db).filter(code="aurora").update(category=_AURORA_CATEGORY)

    for entry in _NEW_THEMES:
        theme = Theme.objects.using(db).create(
            code=entry["code"], name=entry["name"], category=entry["category"], is_active=True
        )
        version = ThemeVersion.objects.using(db).create(
            theme=theme, version_number=1, is_current=True
        )
        ThemePreset.objects.using(db).create(
            theme_version=version,
            name=entry["preset_name"],
            default_settings=entry["default_settings"],
            preview_image_url="",
            is_active=True,
            is_default=False,  # Aurora's preset stays the sole default.
        )


def _unseed(apps, schema_editor):
    db = schema_editor.connection.alias
    Theme = apps.get_model("themes", "Theme")
    Theme.objects.using(db).filter(code__in=[e["code"] for e in _NEW_THEMES]).delete()
    Theme.objects.using(db).filter(code="aurora").update(category="")


class Migration(migrations.Migration):

    dependencies = [
        ("themes", "0002_seed_default_theme"),
    ]

    operations = [
        migrations.AddField(
            model_name="theme",
            name="category",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.RunPython(_seed, _unseed),
    ]
