"""
Seeds exactly one platform-global default trial Plan (+ its current
PlanVersion + quotas/features). Required precondition for
`apps.stores.services.create_store` to succeed AT ALL (Phase 10,
approved architecture decision 12: every Store gets a trial Subscription
provisioned atomically at creation, via
`apps.subscriptions.services.get_default_trial_plan_version` /
`apps.stores.hooks`). Runs automatically as part of `migrate` in every
environment (dev, CI, test) -- the same real-PostgreSQL-migrations
discipline this project already relies on everywhere else, so no test's
`create_store` call needs to know this exists.

Uses the migration's own historical model state (`apps.get_model`), not
a direct import of `apps.subscriptions.models` -- standard Django data-
migration practice, so this keeps working even if the models change
shape in a later migration.
"""

from __future__ import annotations

from django.db import migrations

_PLAN_CODE = "trial"

_QUOTAS = {
    "products": 100,
    "orders_per_period": 500,
    # "staff" is deliberately seeded too, even though no write path
    # enforces it yet (no staff-invite feature exists in Phases 1-9) --
    # approved architecture decision, section 5: model it as real
    # configuration, never claim enforcement coverage that doesn't exist.
    "staff": 5,
}

_FEATURES = {
    "custom_domain": False,
    "api_access": True,
}


def _seed(apps, schema_editor):
    # Explicit `using=schema_editor.connection.alias` throughout -- RunPython's
    # ORM calls do NOT automatically inherit the migration's target database
    # (only DDL/schema operations do, via `MigratorRouter.allow_migrate`).
    # Without this, `.objects.create()` falls back to Django's normal
    # `db_for_write` resolution, which resolves to the "default" alias
    # (app_user) -- wrong role, and during test-DB setup, briefly still
    # pointing at the un-mirrored dev database name (see
    # backend/conftest.py's `django_db_setup` for why "default" mirrors
    # "migrator" only after the migrator's test DB exists).
    db = schema_editor.connection.alias
    Plan = apps.get_model("subscriptions", "Plan")
    PlanVersion = apps.get_model("subscriptions", "PlanVersion")
    PlanVersionFeature = apps.get_model("subscriptions", "PlanVersionFeature")
    PlanVersionQuota = apps.get_model("subscriptions", "PlanVersionQuota")

    plan = Plan.objects.using(db).create(
        code=_PLAN_CODE,
        name="Free Trial",
        is_public=True,
        trial_days=14,
        grace_period_days=3,
        is_default_trial=True,
    )
    version = PlanVersion.objects.using(db).create(
        plan=plan,
        version_number=1,
        price_monthly=0,
        price_yearly=0,
        currency="SAR",
        is_current=True,
    )
    PlanVersionQuota.objects.using(db).bulk_create(
        PlanVersionQuota(plan_version=version, quota_key=key, limit=limit)
        for key, limit in _QUOTAS.items()
    )
    PlanVersionFeature.objects.using(db).bulk_create(
        PlanVersionFeature(plan_version=version, feature_key=key, enabled=enabled)
        for key, enabled in _FEATURES.items()
    )


def _unseed(apps, schema_editor):
    db = schema_editor.connection.alias
    Plan = apps.get_model("subscriptions", "Plan")
    Plan.objects.using(db).filter(code=_PLAN_CODE).delete()  # cascades to PlanVersion/features/quotas


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(_seed, _unseed),
    ]
