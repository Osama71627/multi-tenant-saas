"""
Required test 7 (Phase 11 review round): NotificationTemplate is
platform-global -- app_user reads, app_user cannot mutate. Same proof
shape as Phase 10's apps/subscriptions/tests/test_plan_rls.py (RLS is
the real boundary, not merely the absence of a write policy on paper,
and NOT the PostgreSQL table-level GRANT `app_user` genuinely holds).
"""

from __future__ import annotations

import pytest
from django.db import Error as DjangoDatabaseError
from django.db import connection, transaction

from apps.notifications.models import NotificationTemplate

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded_template() -> NotificationTemplate:
    return NotificationTemplate.objects.get(key="order_confirmation", locale="en")


def test_app_user_can_select_templates(seeded_template):
    assert NotificationTemplate.objects.filter(id=seeded_template.id).exists()


def test_app_user_cannot_insert_a_template():
    with pytest.raises(DjangoDatabaseError):
        with transaction.atomic(using="default"):
            NotificationTemplate.objects.create(
                key="attempted", locale="en", subject="x", body_text="y"
            )


def test_app_user_cannot_update_a_template(seeded_template):
    """UPDATE (unlike INSERT) doesn't raise under RLS -- the row is simply
    invisible to the command, so it matches zero rows. See
    apps/subscriptions/tests/test_plan_rls.py for the full explanation."""
    affected = NotificationTemplate.objects.filter(id=seeded_template.id).update(subject="Hacked")
    assert affected == 0

    seeded_template.refresh_from_db()
    assert seeded_template.subject != "Hacked"


def test_app_user_cannot_delete_a_template(seeded_template):
    deleted_count, _ = NotificationTemplate.objects.filter(id=seeded_template.id).delete()
    assert deleted_count == 0
    assert NotificationTemplate.objects.filter(id=seeded_template.id).exists()


def test_rls_is_enabled_on_notification_template():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity FROM pg_class WHERE relname = %s",
            ["notifications_notificationtemplate"],
        )
        (enabled,) = cursor.fetchone()
    assert enabled is True


def test_app_user_has_table_level_write_grant_but_rls_still_blocks(seeded_template):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_table_privilege('app_user', 'notifications_notificationtemplate', 'INSERT')"
        )
        (has_insert_grant,) = cursor.fetchone()
    assert has_insert_grant is True  # the blanket table-level GRANT genuinely exists

    with pytest.raises(DjangoDatabaseError):
        with transaction.atomic(using="default"):
            NotificationTemplate.objects.create(
                key="grant-vs-rls", locale="en", subject="x", body_text="y"
            )
