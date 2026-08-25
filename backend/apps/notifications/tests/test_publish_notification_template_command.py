"""
Coverage for `publish_notification_template` itself (previously 0% --
every other test exercises it only indirectly via mocking, per the
cross-connection-visibility note in test_localization.py). Same shape as
apps/subscriptions/tests/test_plan_version_isolation.py's coverage of
`publish_plan_version`: reject writing through anything but the migrator
alias, then verify the upsert semantics via that same alias (never via
"default" -- app_user has no write policy on NotificationTemplate at
all, proven in test_template_rls.py).
"""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.notifications.models import NotificationTemplate

pytestmark = pytest.mark.django_db(databases=["default", "migrator"])


def test_command_rejects_the_default_database_alias():
    with pytest.raises(CommandError, match="migrator"):
        call_command(
            "publish_notification_template",
            key="order_confirmation",
            locale="en",
            subject="x",
            body_text="y",
        )


def test_command_creates_a_new_template_via_the_migrator_alias():
    call_command(
        "publish_notification_template",
        database="migrator",
        key="password_reset_test_only",
        locale="en",
        subject="Reset your password",
        body_text="Click here: $reset_link",
    )
    try:
        template = NotificationTemplate.objects.using("migrator").get(
            key="password_reset_test_only", locale="en"
        )
        assert template.subject == "Reset your password"
        assert template.is_active is True
    finally:
        NotificationTemplate.objects.using("migrator").filter(
            key="password_reset_test_only", locale="en"
        ).delete()


def test_command_upserts_in_place_on_a_second_publish():
    call_command(
        "publish_notification_template",
        database="migrator",
        key="password_reset_test_only",
        locale="en",
        subject="v1 subject",
        body_text="v1 body",
    )
    try:
        first = NotificationTemplate.objects.using("migrator").get(
            key="password_reset_test_only", locale="en"
        )

        call_command(
            "publish_notification_template",
            database="migrator",
            key="password_reset_test_only",
            locale="en",
            subject="v2 subject",
            body_text="v2 body",
        )
        second = NotificationTemplate.objects.using("migrator").get(
            key="password_reset_test_only", locale="en"
        )

        assert second.id == first.id  # same logical row, updated in place -- no duplicate
        assert second.subject == "v2 subject"
    finally:
        NotificationTemplate.objects.using("migrator").filter(
            key="password_reset_test_only", locale="en"
        ).delete()


def test_command_inactive_flag_publishes_a_disabled_template():
    call_command(
        "publish_notification_template",
        database="migrator",
        key="password_reset_test_only",
        locale="en",
        subject="x",
        body_text="y",
        inactive=True,
    )
    try:
        template = NotificationTemplate.objects.using("migrator").get(
            key="password_reset_test_only", locale="en"
        )
        assert template.is_active is False
    finally:
        NotificationTemplate.objects.using("migrator").filter(
            key="password_reset_test_only", locale="en"
        ).delete()
