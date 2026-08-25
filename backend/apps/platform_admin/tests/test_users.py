from __future__ import annotations

import pytest

from apps.platform_admin import services
from apps.platform_admin.tests.mfa_test_helpers import (
    create_and_authenticate_platform_staff as _staff_client,
)

pytestmark = pytest.mark.django_db(databases=["default", "platform"])


def test_list_users(make_platform_staff_user):
    make_platform_staff_user("merchant-a@example.com", is_platform_staff=False)
    make_platform_staff_user("merchant-b@example.com", is_platform_staff=False)

    emails = {u.email for u in services.list_users()}
    assert "merchant-a@example.com" in emails
    assert "merchant-b@example.com" in emails


def test_get_user_detail(make_platform_staff_user):
    user = make_platform_staff_user("detail@example.com", is_platform_staff=False)
    fetched = services.get_user(user.id)
    assert fetched.email == "detail@example.com"


def test_users_list_via_http(make_platform_staff_user):
    make_platform_staff_user("http-user@example.com", is_platform_staff=False)
    client = _staff_client("users-http-staff@example.com")

    response = client.get("/api/v1/platform/users")
    assert response.status_code == 200
    assert any(row["email"] == "http-user@example.com" for row in response.data)
