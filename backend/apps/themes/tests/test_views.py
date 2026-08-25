"""
HTTP-level coverage for apps.themes' two Phase-12 read endpoints. Runs
against real PostgreSQL (RLS enforced by the DB itself, not simulated).
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.themes.models import ThemePreset

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return PlatformUser.objects.create_user(
        email="theme-views-owner@example.com", password="correct-h0rse!"  # noqa: S106
    )


@pytest.fixture
def client(user):
    api_client = APIClient()
    login = api_client.post(
        "/api/v1/auth/login", {"email": user.email, "password": "correct-h0rse!"}, format="json"
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return api_client


def test_theme_preset_list_requires_authentication():
    response = APIClient().get("/api/v1/dashboard/theme-presets")
    assert response.status_code == 401


def test_theme_preset_list_returns_the_seeded_default(client):
    response = client.get("/api/v1/dashboard/theme-presets")
    assert response.status_code == 200
    names = [p["name"] for p in response.data]
    assert "Default" in names
    default_entry = next(p for p in response.data if p["name"] == "Default")
    assert default_entry["is_default"] is True
    assert default_entry["theme_code"] == "aurora"
    assert default_entry["theme_version_number"] == 1
    assert "primary_color" in default_entry["default_settings"]


def test_theme_preset_list_excludes_inactive_presets(client):
    ThemePreset.objects.filter(is_default=True).count()  # sanity: readable
    response = client.get("/api/v1/dashboard/theme-presets")
    for preset in response.data:
        # every returned preset is one this test can independently
        # confirm is_active for, via the same read policy the view uses
        assert ThemePreset.objects.get(id=preset["id"]).is_active is True


def test_store_theme_config_reflects_the_provisioned_default(client):
    create_response = client.post(
        "/api/v1/dashboard/stores",
        {"name": "Theme View Co", "slug": "theme-view-co"},
        format="json",
    )
    assert create_response.status_code == 201, create_response.data
    store_id = create_response.data["id"]

    response = client.get(f"/api/v1/dashboard/stores/{store_id}/theme")
    assert response.status_code == 200
    assert response.data["theme_code"] == "aurora"
    assert response.data["theme_version_number"] == 1
    assert response.data["settings"]["primary_color"] == "#111827"


def test_store_theme_config_reflects_an_explicit_preset_choice(client):
    preset = ThemePreset.objects.get(is_default=True)
    create_response = client.post(
        "/api/v1/dashboard/stores",
        {"name": "Theme Choice Co", "slug": "theme-choice-co", "theme_preset_id": str(preset.id)},
        format="json",
    )
    assert create_response.status_code == 201, create_response.data
    store_id = create_response.data["id"]

    response = client.get(f"/api/v1/dashboard/stores/{store_id}/theme")
    assert response.status_code == 200
    assert response.data["theme_code"] == preset.theme_version.theme.code


def test_store_creation_rejects_an_unknown_theme_preset_id():
    user = PlatformUser.objects.create_user(
        email="theme-reject-owner@example.com", password="correct-h0rse!"  # noqa: S106
    )
    api_client = APIClient()
    login = api_client.post(
        "/api/v1/auth/login", {"email": user.email, "password": "correct-h0rse!"}, format="json"
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    response = api_client.post(
        "/api/v1/dashboard/stores",
        {
            "name": "Theme Reject Co",
            "slug": "theme-reject-co",
            "theme_preset_id": "01a02dab-0000-7000-8000-000000000000",
        },
        format="json",
    )
    assert response.status_code == 400
