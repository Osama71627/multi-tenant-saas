"""Dashboard provider-config CRUD -- write-only secrets (docs/ARCHITECTURE.md
section 8.3: "لا endpoint يعيد السر إطلاقًا")."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def test_create_provider_config_never_returns_the_secret(store_with_hostname):
    ctx = store_with_hostname
    response = ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/payments/providers",
        {
            "provider_key": "stripe",
            "mode": "test",
            "is_enabled": True,
            "credentials": "sk_test_51H8xyzABCDEF9f2c",
            "webhook_secret": "whsec_abcdef123456",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    body_str = str(response.data)
    assert "sk_test_51H8xyzABCDEF9f2c" not in body_str
    assert "whsec_abcdef123456" not in body_str
    assert response.data["credentials_hint"] == "****9f2c"


def test_list_provider_configs_never_returns_secrets(store_with_hostname):
    ctx = store_with_hostname
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/payments/providers",
        {"provider_key": "mock", "credentials": "not-actually-secret-but-still-hidden"},
        format="json",
    )
    response = ctx["dashboard_client"].get(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/payments/providers"
    )
    assert response.status_code == 200
    assert "not-actually-secret-but-still-hidden" not in str(response.data)


def test_credentials_are_actually_encrypted_in_the_database(store_with_hostname):
    from apps.payments.models import StoreProviderConfig
    from apps.payments.tests.conftest import store_db_context

    ctx = store_with_hostname
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/payments/providers",
        {"provider_key": "stripe", "credentials": "sk_test_plaintext_marker_xyz"},
        format="json",
    )
    with store_db_context(ctx["store"]):
        config = StoreProviderConfig.objects.get(provider_key="stripe")
        assert "sk_test_plaintext_marker_xyz" not in config.credentials_encrypted
        assert config.credentials_encrypted.startswith("v1:")


def test_duplicate_provider_config_for_same_store_is_rejected(store_with_hostname):
    ctx = store_with_hostname
    ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/payments/providers",
        {"provider_key": "mock"},
        format="json",
    )
    response = ctx["dashboard_client"].post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/payments/providers",
        {"provider_key": "mock"},
        format="json",
    )
    assert response.status_code == 400


def test_non_member_cannot_manage_provider_configs(store_with_hostname):
    from apps.payments.tests.conftest import make_client_for

    ctx = store_with_hostname
    outsider_client, _outsider = make_client_for("provider-config-outsider@example.com")
    response = outsider_client.post(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/payments/providers",
        {"provider_key": "mock"},
        format="json",
    )
    assert response.status_code == 403
