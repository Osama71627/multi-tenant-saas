"""
Required test 9 (Phase 11 review round): message-language resolution is
deterministic, with a clear fallback and no silent crash. Phase 11 has
no real per-store language preference yet (approved review-round scope
-- `Store` has no `default_language` field, so `resolve_locale` always
resolves to the platform default today); this exercises the fallback
machinery itself directly (`apps.notifications.services._get_template`)
rather than waiting on a field that doesn't exist yet.

Note: `NotificationTemplate` writes only ever go through the migrator
alias (approved global-readonly RLS, apps/notifications/management/
commands/publish_notification_template.py) -- a genuinely separate DB
connection from "default". Under this project's savepoint-based test
isolation (`transaction=True` deliberately avoided project-wide: app_user
lacks TRUNCATE, see apps/orders/tests/test_concurrency.py), an uncommitted
migrator-alias write is invisible to "default" reads within the same
test. So the "unconfigured template" failure path below is proven via
`unittest.mock.patch` on `_get_template` -- the same mocking shape
apps/notifications/tests/test_dispatch_idempotency.py already uses for
its EmailChannel failure-path tests -- rather than a live DB mutation.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.conf import settings
from django.core import mail

from apps.notifications import services
from apps.notifications.tests.conftest import build_confirmed_order, store_db_context

pytestmark = pytest.mark.django_db


def test_resolve_locale_defaults_to_platform_language_code(variant_in_store):
    store = variant_in_store["store"]
    assert not hasattr(store, "default_language")  # nothing sets this yet -- documents the gap
    assert services.resolve_locale(store) == settings.LANGUAGE_CODE


def test_get_template_falls_back_to_platform_default_locale():
    # Only "en" is seeded (apps/notifications/migrations/0002_...); asking
    # for a locale that doesn't exist must fall back to the platform
    # default rather than raising.
    template = services._get_template(key="order_confirmation", locale="fr")
    assert template.locale == settings.LANGUAGE_CODE


def test_get_template_raises_a_clear_configuration_error_when_nothing_matches():
    with pytest.raises(services.TemplateNotConfiguredError):
        services._get_template(key="no_such_notification_key", locale="fr")


def test_missing_template_fails_the_dispatch_terminally_without_crashing_the_task(
    variant_in_store, storefront_client
):
    """No silent crash: an unconfigured template must not propagate an
    unhandled exception out of the Celery task -- it's recorded as a
    terminal FAILED dispatch instead (apps.notifications.services.
    process_committed_event's TemplateNotConfiguredError branch)."""
    ctx = variant_in_store
    mail.outbox.clear()

    with patch(
        "apps.notifications.services._get_template",
        side_effect=services.TemplateNotConfiguredError(
            "no active template for order_confirmation"
        ),
    ):
        order_data = build_confirmed_order(
            ctx, storefront_client, idempotency_key="localization-gap-1"
        )

    with store_db_context(ctx["store"]):
        from apps.core.models import EventLog
        from apps.notifications.models import NotificationDispatch

        event = EventLog.objects.filter(
            event_type="order.confirmed", payload__aggregate_id=order_data["id"]
        ).get()
        dispatch = NotificationDispatch.objects.get(
            event=event, notification_type="order_confirmation"
        )
    assert dispatch.status == NotificationDispatch.Status.FAILED
    assert "order_confirmation" in dispatch.last_error
    assert len(mail.outbox) == 0
