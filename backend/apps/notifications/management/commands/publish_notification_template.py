"""
Administrative setup script for publishing/updating a `NotificationTemplate`
-- same boundary as Phase 10's `publish_plan_version`
(apps/subscriptions/management/commands/publish_plan_version.py):
`NotificationTemplate` has no write policy for `app_user` at all
(approved architecture decision, mirroring Phase 10's Plan tables), and
`app_migrator` is for schema/controlled-setup only, never a runtime
business-mutation path opened by application code. This command is a
human-operator action (`python manage.py publish_notification_template
--database=migrator ...`), never imported or called by request-serving
code.

Templates are upserted by `(key, locale)` -- publishing again with the
same key/locale updates the existing row in place (unlike Phase 10's
`PlanVersion`, a template has no "existing Subscriptions depend on the
old wording" concern, so there is nothing to version).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DEFAULT_DB_ALIAS

from apps.notifications.models import NotificationTemplate


class Command(BaseCommand):
    help = "Publishes or updates a NotificationTemplate (administrative-only)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help="Must be 'migrator' -- NotificationTemplate has no app_user write policy.",
        )
        parser.add_argument("--key", required=True, help='e.g. "order_confirmation".')
        parser.add_argument("--locale", required=True, help='e.g. "en".')
        parser.add_argument("--subject", required=True)
        parser.add_argument("--body-text", required=True)
        parser.add_argument("--inactive", action="store_true", help="Publish as inactive.")

    def handle(self, *args, **options) -> None:
        db = options["database"]
        if db != "migrator":
            raise CommandError(
                "This command must run against the migrator alias: add "
                "--database=migrator (NotificationTemplate has no app_user write policy)."
            )

        template, created = NotificationTemplate.objects.using(db).update_or_create(
            key=options["key"],
            locale=options["locale"],
            defaults={
                "subject": options["subject"],
                "body_text": options["body_text"],
                "is_active": not options["inactive"],
            },
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} template {template.key}/{template.locale} (id={template.id})"
            )
        )
