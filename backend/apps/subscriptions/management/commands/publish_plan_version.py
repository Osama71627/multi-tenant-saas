"""
Administrative setup script for publishing a new `PlanVersion`.

Deliberately NOT a callable service function under `apps.subscriptions.
services` (the review-round-approved boundary, docs/PHASE_10_REPORT.md):
`Plan`/`PlanVersion`/`PlanVersionFeature`/`PlanVersionQuota` have no
write policy for `app_user` at all (approved architecture decision 1),
and `app_migrator` exists to run controlled schema migrations and
seed/setup data -- not to serve as a runtime platform-admin bypass that
ordinary application code (or a service function reachable from a view)
could open on demand. A Django management command is explicitly a
human-operator-run administrative action (`python manage.py
publish_plan_version ...`, run by whoever holds `MIGRATOR_DATABASE_URL`
credentials), the same category as `manage.py migrate` itself -- never
imported or called by request-serving code.

Until a reviewed Platform Admin write architecture exists (its own
future roadmap phase), this -- plus migrations/fixtures -- is the ONLY
way Plan data changes. `Subscription.plan_version`/`scheduled_plan_version`
(app_user-writable, standard RLS) are moved separately via
`apps.subscriptions.services.upgrade_subscription`/`schedule_downgrade`,
which only need read access to whatever PlanVersion this command
publishes (Plan tables keep an open `SELECT` policy for everyone).

Example:

    python manage.py publish_plan_version --database=migrator \\
        --plan-code=trial --price-monthly=0 --price-yearly=0 \\
        --quotas='{"products": 100, "orders_per_period": 500}' \\
        --features='{"api_access": true, "custom_domain": false}'

`--database=migrator` is required (Django's own guard, not this
command's) -- `MigratorRouter.allow_migrate` and this command's explicit
`.using(db)` calls both key off the SAME alias the operator passes in,
so there's no way to run this against `app_user`'s connection instead.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DEFAULT_DB_ALIAS, transaction

from apps.subscriptions.models import Plan, PlanVersion, PlanVersionFeature, PlanVersionQuota


class Command(BaseCommand):
    help = "Publishes a new, immutable PlanVersion for an existing Plan (administrative-only)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help="Must be 'migrator' -- Plan/PlanVersion have no app_user write policy.",
        )
        parser.add_argument("--plan-code", required=True, help="Existing Plan.code.")
        parser.add_argument("--price-monthly", type=int, required=True, help="Minor units.")
        parser.add_argument("--price-yearly", type=int, required=True, help="Minor units.")
        parser.add_argument("--currency", default="SAR")
        parser.add_argument(
            "--quotas",
            default="{}",
            help='JSON object, e.g. \'{"products": 100, "orders_per_period": null}\' '
            "(null = unlimited).",
        )
        parser.add_argument(
            "--features",
            default="{}",
            help='JSON object, e.g. \'{"api_access": true, "custom_domain": false}\'.',
        )
        parser.add_argument(
            "--no-current",
            action="store_true",
            help="Publish the version WITHOUT marking it the Plan's current one "
            "(new/renewing Subscriptions keep resolving to whatever version is "
            "already is_current=True).",
        )

    def handle(self, *args, **options) -> None:
        db = options["database"]
        if db != "migrator":
            raise CommandError(
                "This command must run against the migrator alias: "
                "add --database=migrator (Plan/PlanVersion have no app_user write policy)."
            )

        try:
            quotas: dict[str, int | None] = json.loads(options["quotas"])
        except json.JSONDecodeError as exc:
            raise CommandError(f"--quotas is not valid JSON: {exc}") from exc
        try:
            features: dict[str, bool] = json.loads(options["features"])
        except json.JSONDecodeError as exc:
            raise CommandError(f"--features is not valid JSON: {exc}") from exc

        try:
            plan = Plan.objects.using(db).get(code=options["plan_code"])
        except Plan.DoesNotExist as exc:
            raise CommandError(f"No Plan with code={options['plan_code']!r}.") from exc

        make_current = not options["no_current"]

        with transaction.atomic(using=db):
            next_number = (
                PlanVersion.objects.using(db)
                .filter(plan=plan)
                .order_by("-version_number")
                .values_list("version_number", flat=True)
                .first()
                or 0
            ) + 1
            if make_current:
                PlanVersion.objects.using(db).filter(plan=plan, is_current=True).update(
                    is_current=False
                )
            version = PlanVersion.objects.using(db).create(
                plan=plan,
                version_number=next_number,
                price_monthly=options["price_monthly"],
                price_yearly=options["price_yearly"],
                currency=options["currency"],
                is_current=make_current,
            )
            for feature_key, enabled in features.items():
                PlanVersionFeature.objects.using(db).create(
                    plan_version=version, feature_key=feature_key, enabled=enabled
                )
            for quota_key, limit in quotas.items():
                PlanVersionQuota.objects.using(db).create(
                    plan_version=version, quota_key=quota_key, limit=limit
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Published {plan.code} v{version.version_number} "
                f"(id={version.id}, current={make_current})"
            )
        )
