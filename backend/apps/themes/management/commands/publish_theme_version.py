"""
Administrative setup script for publishing a new, immutable `ThemeVersion`
for an existing `Theme` (administrative-only, same boundary as Phase 10's
`publish_plan_version`): `Theme`/`ThemeVersion`/`ThemePreset` have no
write policy for `app_user` at all -- `app_migrator` runs controlled
schema migrations and seed/setup data, never a runtime platform-admin
bypass reachable from request-serving code. See
apps/subscriptions/management/commands/publish_plan_version.py's
docstring for the full reasoning; this mirrors it exactly.

Example:

    python manage.py publish_theme_version --database=migrator \\
        --theme-code=aurora
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DEFAULT_DB_ALIAS, transaction

from apps.themes.models import Theme, ThemeVersion


class Command(BaseCommand):
    help = "Publishes a new, immutable ThemeVersion for an existing Theme (administrative-only)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help="Must be 'migrator' -- Theme/ThemeVersion have no app_user write policy.",
        )
        parser.add_argument("--theme-code", required=True, help="Existing Theme.code.")
        parser.add_argument(
            "--no-current",
            action="store_true",
            help="Publish the version WITHOUT marking it the Theme's current one "
            "(new provisioning keeps resolving to whatever version is already "
            "is_current=True).",
        )

    def handle(self, *args, **options) -> None:
        db = options["database"]
        if db != "migrator":
            raise CommandError(
                "This command must run against the migrator alias: "
                "add --database=migrator (Theme/ThemeVersion have no app_user write policy)."
            )

        try:
            theme = Theme.objects.using(db).get(code=options["theme_code"])
        except Theme.DoesNotExist as exc:
            raise CommandError(f"No Theme with code={options['theme_code']!r}.") from exc

        make_current = not options["no_current"]

        with transaction.atomic(using=db):
            next_number = (
                ThemeVersion.objects.using(db)
                .filter(theme=theme)
                .order_by("-version_number")
                .values_list("version_number", flat=True)
                .first()
                or 0
            ) + 1
            if make_current:
                ThemeVersion.objects.using(db).filter(theme=theme, is_current=True).update(
                    is_current=False
                )
            version = ThemeVersion.objects.using(db).create(
                theme=theme, version_number=next_number, is_current=make_current
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Published {theme.code} v{version.version_number} "
                f"(id={version.id}, current={make_current})"
            )
        )
