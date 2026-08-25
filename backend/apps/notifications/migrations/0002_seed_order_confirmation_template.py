"""
Seeds the platform-default "order_confirmation" template for the
platform's default locale (`settings.LANGUAGE_CODE`, "en"). Required
precondition for the Phase 11 DoD ("order confirmation email arrives")
to work at all out of the box -- runs automatically as part of `migrate`
in every environment, same discipline as Phase 10's
`0002_seed_default_trial_plan.py`.

Explicit `using=schema_editor.connection.alias` throughout -- RunPython's
ORM calls do NOT automatically inherit the migration's target database;
see apps/subscriptions/migrations/0002_seed_default_trial_plan.py's
docstring for the full explanation of why this matters.

Only `$name`-style placeholders (apps/notifications/rendering.py's
`string.Template` substitution) -- no HTML, no arbitrary markup.
"""

from __future__ import annotations

from django.db import migrations

_KEY = "order_confirmation"
_LOCALE = "en"
_SUBJECT = "Your order $order_number is confirmed"
_BODY = (
    "Hi,\n\n"
    "Thanks for your order at $store_name!\n\n"
    "Order number: $order_number\n"
    "Total: $order_total\n\n"
    "We'll let you know once it ships.\n\n"
    "$store_name"
)


def _seed(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    NotificationTemplate.objects.using(schema_editor.connection.alias).create(
        key=_KEY, locale=_LOCALE, subject=_SUBJECT, body_text=_BODY, is_active=True
    )


def _unseed(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    NotificationTemplate.objects.using(schema_editor.connection.alias).filter(
        key=_KEY, locale=_LOCALE
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(_seed, _unseed),
    ]
