"""Phase 17: Content-Security-Policy + Permissions-Policy on every
Django response, with the one documented /admin/-only relaxation."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def test_api_response_carries_strict_csp(client):
    response = client.get("/api/v1/auth/me")
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp


def test_api_response_carries_permissions_policy(client):
    response = client.get("/api/v1/auth/me")
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"


def test_admin_response_uses_the_relaxed_admin_csp(client):
    response = client.get("/admin/login/")
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "unsafe-inline" in csp


def test_admin_csp_never_allows_unsafe_eval(client):
    response = client.get("/admin/login/")
    assert "unsafe-eval" not in response.headers["Content-Security-Policy"]
