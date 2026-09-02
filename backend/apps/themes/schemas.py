"""
Allowlisted validation for `StoreThemeConfig.settings` -- the approved
Theme/Template decision's non-negotiable: "All settings writes must be
validated against the allowed ThemeVersion settings contract", no
arbitrary JSON keys, no arbitrary HTML/CSS/JS. Same shape as Phase 11's
notification-rendering allowlist: an explicit serializer defines exactly
what's accepted, everything else is rejected outright (not silently
dropped -- a typo'd or malicious key must fail validation, not vanish).

Keyed by `(theme.code, theme_version.version_number)`, not by theme alone
-- a new ThemeVersion is free to change its settings shape entirely
without touching what earlier, still-pinned versions accept (mirrors
`ThemeVersion` being immutable once published).
"""

from __future__ import annotations

from rest_framework import serializers

_ALLOWED_FONTS = ["inter", "cairo", "tajawal"]
_ALLOWED_HOMEPAGE_SECTIONS = ["hero", "featured_products", "categories", "newsletter"]
_ALLOWED_NAV_ITEMS = ["shop", "about", "contact"]
_HEX_COLOR_RE = r"^#[0-9a-fA-F]{6}$"


class AuroraV1SettingsSerializer(serializers.Serializer):
    primary_color = serializers.RegexField(_HEX_COLOR_RE, default="#111827")
    secondary_color = serializers.RegexField(_HEX_COLOR_RE, default="#6B7280")
    accent_color = serializers.RegexField(_HEX_COLOR_RE, default="#2563EB")
    font_choice = serializers.ChoiceField(choices=_ALLOWED_FONTS, default="inter")
    hero_headline = serializers.CharField(max_length=140, allow_blank=True, default="")
    hero_subheadline = serializers.CharField(max_length=280, allow_blank=True, default="")
    homepage_sections = serializers.ListField(
        child=serializers.ChoiceField(choices=_ALLOWED_HOMEPAGE_SECTIONS),
        default=list,
    )
    nav_order = serializers.ListField(
        child=serializers.ChoiceField(choices=_ALLOWED_NAV_ITEMS),
        default=list,
    )


_SETTINGS_SERIALIZERS: dict[tuple[str, int], type[serializers.Serializer]] = {
    ("aurora", 1): AuroraV1SettingsSerializer,
    # Phase B: Fashion/Electronics/Luxury are genuinely different
    # frontend component packages (@saas/theme-fashion/-electronics/
    # -luxury), but the SETTINGS CONTRACT a merchant configures --
    # palette, font choice, hero copy, homepage section order, nav
    # order -- is deliberately the same shape as Aurora's. What a theme
    # changes is the RENDERING of those settings, not what's
    # configurable; reusing this one serializer class for all four
    # keys validates each identically without three pointless
    # duplicate classes. A theme that later needs its own distinct
    # configurable fields gets its own serializer then, same as this
    # dict already supports per (code, version) key.
    ("fashion", 1): AuroraV1SettingsSerializer,
    ("electronics", 1): AuroraV1SettingsSerializer,
    ("luxury", 1): AuroraV1SettingsSerializer,
    # Phase B follow-up: HomeStore (@saas/theme-homestore) -- same
    # reasoning, same shared contract, a genuinely different rendering.
    ("homestore", 1): AuroraV1SettingsSerializer,
}


class UnknownThemeContractError(Exception):
    """No settings serializer registered for this (theme code, version)
    pair -- a deployment/registration gap, not a user-facing error."""


def get_settings_serializer_class(
    *, theme_code: str, version_number: int
) -> type[serializers.Serializer]:
    try:
        return _SETTINGS_SERIALIZERS[(theme_code, version_number)]
    except KeyError as exc:
        raise UnknownThemeContractError(
            f"No settings contract registered for theme={theme_code!r} "
            f"version={version_number!r}."
        ) from exc


def validate_settings(*, theme_code: str, version_number: int, data: dict) -> dict:
    """Raises `rest_framework.exceptions.ValidationError` on any
    unexpected/invalid key -- callers decide how to surface that."""
    serializer_cls = get_settings_serializer_class(
        theme_code=theme_code, version_number=version_number
    )
    serializer = serializer_cls(data=data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)
