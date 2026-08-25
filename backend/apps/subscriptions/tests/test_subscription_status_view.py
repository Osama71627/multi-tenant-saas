"""
Phase 12 (dashboard subscription-status UI): `GET /api/v1/dashboard/
stores/{store_id}/subscription` -- read-only, reflects the trial
Subscription every store already gets atomically at creation
(apps.subscriptions.services.provision_trial_subscription).
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlatformUser
from apps.stores.services import create_store

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner_client():
    owner = PlatformUser.objects.create_user(
        email="sub-status-owner@example.com", password="correct-h0rse!"  # noqa: S106
    )
    store = create_store(owner=owner, name="Sub Status Co", slug="sub-status-co")
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login",
        {"email": "sub-status-owner@example.com", "password": "correct-h0rse!"},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client, store


def test_returns_the_stores_trial_subscription(owner_client):
    client, store = owner_client
    response = client.get(f"/api/v1/dashboard/stores/{store.id}/subscription")
    assert response.status_code == 200
    assert response.data["status"] == "trialing"
    assert response.data["plan_code"] == "trial"
    assert response.data["trial_ends_at"] is not None


def test_requires_membership_in_the_store():
    PlatformUser.objects.create_user(
        email="sub-status-other@example.com", password="correct-h0rse!"  # noqa: S106
    )
    owner = PlatformUser.objects.create_user(
        email="sub-status-owner-2@example.com", password="correct-h0rse!"  # noqa: S106
    )
    store = create_store(owner=owner, name="Sub Status Co 2", slug="sub-status-co-2")

    client = APIClient()
    login = client.post(
        "/api/v1/auth/login",
        {"email": "sub-status-other@example.com", "password": "correct-h0rse!"},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    response = client.get(f"/api/v1/dashboard/stores/{store.id}/subscription")
    assert response.status_code == 403


def test_unauthenticated_request_is_rejected():
    response = APIClient().get(
        "/api/v1/dashboard/stores/01a02ec6-0000-7000-8000-000000000000/subscription"
    )
    assert response.status_code == 401
