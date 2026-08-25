"""
The approved decision's non-negotiable: "All settings writes must be
validated against the allowed ThemeVersion settings contract" -- no
arbitrary JSON keys, no arbitrary HTML/CSS/JS.
"""

from __future__ import annotations

import pytest
from rest_framework.exceptions import ValidationError

from apps.themes.schemas import UnknownThemeContractError, validate_settings

_VALID = {
    "primary_color": "#111827",
    "secondary_color": "#6B7280",
    "accent_color": "#2563EB",
    "font_choice": "inter",
    "hero_headline": "Hello",
    "hero_subheadline": "World",
    "homepage_sections": ["hero", "featured_products"],
    "nav_order": ["shop", "about"],
}


def test_valid_settings_pass_through():
    result = validate_settings(theme_code="aurora", version_number=1, data=_VALID)
    assert result["primary_color"] == "#111827"
    assert result["homepage_sections"] == ["hero", "featured_products"]


def test_unknown_theme_contract_raises_clearly():
    with pytest.raises(UnknownThemeContractError):
        validate_settings(theme_code="does-not-exist", version_number=1, data=_VALID)


def test_invalid_hex_color_is_rejected():
    bad = {**_VALID, "primary_color": "not-a-color"}
    with pytest.raises(ValidationError):
        validate_settings(theme_code="aurora", version_number=1, data=bad)


def test_disallowed_homepage_section_is_rejected():
    bad = {**_VALID, "homepage_sections": ["hero", "arbitrary_iframe_injection"]}
    with pytest.raises(ValidationError):
        validate_settings(theme_code="aurora", version_number=1, data=bad)


def test_unknown_extra_key_does_not_leak_into_validated_data():
    """DRF Serializer silently drops unrecognized input keys rather than
    raising (there's no allowlisted field for them to populate) -- proven
    explicitly here so an unexpected key (e.g. `raw_html`) can never end
    up persisted into `StoreThemeConfig.settings`."""
    sneaky = {**_VALID, "raw_html": "<script>alert(1)</script>"}
    result = validate_settings(theme_code="aurora", version_number=1, data=sneaky)
    assert "raw_html" not in result
