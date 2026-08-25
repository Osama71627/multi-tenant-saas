"""
Administrative setup script for publishing/updating a `ThemePreset`
(upsert by `theme_version` + `name`) -- same boundary as
`publish_theme_version`/Phase 11's `publish_notification_template`.
`default_settings` is validated against the target ThemeVersion's real
settings contract (apps/themes/schemas.py) before being written, so an
operator can't publish a preset the provisioning path would later fail
to validate.

Example:

    python manage.py publish_theme_preset --database=migrator \\
        --theme-code=aurora --theme-version=1 --name="Ocean Blue" \\
        --theme-settings='{"primary_color": "#0EA5E9", ...}' --default
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DEFAULT_DB_ALIAS, transaction

from apps.themes.models import ThemePreset, ThemeVersion
from apps.themes.schemas import UnknownThemeContractError, validate_settings


class Command(BaseCommand):
    help = "Publishes or updates a ThemePreset for an existing ThemeVersion (administrative-only)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help="Must be 'migrator' -- ThemePreset has no app_user write policy.",
        )
        parser.add_argument("--theme-code", required=True, help="Existing Theme.code.")
        parser.add_argument(
            "--theme-version", type=int, required=True, help="ThemeVersion.version_number."
        )
        parser.add_argument("--name", required=True)
        parser.add_argument("--theme-settings", required=True, help="JSON object.")
        parser.add_argument("--preview-image-url", default="")
        parser.add_argument("--inactive", action="store_true", help="Publish as inactive.")
        parser.add_argument(
            "--default",
            action="store_true",
            help="Make this the platform default preset (unsets any previous default).",
        )

    def handle(self, *args, **options) -> None:
        db = options["database"]
        if db != "migrator":
            raise CommandError(
                "This command must run against the migrator alias: "
                "add --database=migrator (ThemePreset has no app_user write policy)."
            )

        try:
            settings_data = json.loads(options["theme_settings"])
        except json.JSONDecodeError as exc:
            raise CommandError(f"--theme-settings is not valid JSON: {exc}") from exc

        try:
            theme_version = ThemeVersion.objects.using(db).get(
                theme__code=options["theme_code"], version_number=options["theme_version"]
            )
        except ThemeVersion.DoesNotExist as exc:
            raise CommandError(
                f"No ThemeVersion for theme={options['theme_code']!r} "
                f"version={options['theme_version']!r}."
            ) from exc

        try:
            validated_settings = validate_settings(
                theme_code=options["theme_code"],
                version_number=options["theme_version"],
                data=settings_data,
            )
        except UnknownThemeContractError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 -- surface DRF ValidationError details plainly
            raise CommandError(f"--theme-settings failed validation: {exc}") from exc

        make_default = options["default"]

        with transaction.atomic(using=db):
            if make_default:
                ThemePreset.objects.using(db).filter(is_default=True).update(is_default=False)
            preset, created = ThemePreset.objects.using(db).update_or_create(
                theme_version=theme_version,
                name=options["name"],
                defaults={
                    "default_settings": validated_settings,
                    "preview_image_url": options["preview_image_url"],
                    "is_active": not options["inactive"],
                    "is_default": make_default,
                },
            )

        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} preset {preset.name!r} for {options['theme_code']} "
                f"v{options['theme_version']} (id={preset.id}, default={make_default})"
            )
        )
