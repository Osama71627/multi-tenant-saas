"""
Phase D ("product vision reset" -- Plan Selection): seeds the first
real, public, PAID plans. Same discipline as
0002_seed_default_trial_plan.py -- runs automatically as part of
`migrate` in every environment (dev, CI, test), so no test needs to
know this exists, and the public plan-selection screen has real,
non-fabricated data from the moment the migration lands rather than
depending on a manual `publish_plan_version` run afterwards.

Deliberately not "included theme" on any plan -- theme selection and
SaaS subscription stay separate concepts, per the approved product
vision: a merchant picks a theme independently on the public
marketplace (apps.themes) and a plan here; nothing in `Plan`/
`PlanVersion` references a theme at all (and structurally can't --
apps.subscriptions may not import apps.themes, see the "Layering:
subscriptions does not depend on catalog" contract in pyproject.toml).

Prices are real configured values now that they're seeded (minor
units, matching every other money field in this project) -- not
placeholders left unset for the frontend to invent.
"""

from __future__ import annotations

from django.db import migrations

_PLANS = [
    {
        "code": "basic",
        "name": "Basic",
        "price_monthly": 9900,
        "price_yearly": 99000,
        "quotas": {"products": 50, "orders_per_period": 200, "staff": 1},
        "features": {"api_access": False, "custom_domain": False},
    },
    {
        "code": "professional",
        "name": "Professional",
        "price_monthly": 19900,
        "price_yearly": 199000,
        "quotas": {"products": 500, "orders_per_period": 2000, "staff": 5},
        "features": {"api_access": True, "custom_domain": False},
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "price_monthly": 49900,
        "price_yearly": 499000,
        # `None` = unlimited (apps.subscriptions.entitlements.check_quota's
        # existing convention -- see PlanVersionQuota.limit's own
        # docstring in models.py).
        "quotas": {"products": None, "orders_per_period": None, "staff": None},
        "features": {"api_access": True, "custom_domain": True},
    },
]

_CURRENCY = "SAR"


def _seed(apps, schema_editor):
    db = schema_editor.connection.alias
    Plan = apps.get_model("subscriptions", "Plan")
    PlanVersion = apps.get_model("subscriptions", "PlanVersion")
    PlanVersionFeature = apps.get_model("subscriptions", "PlanVersionFeature")
    PlanVersionQuota = apps.get_model("subscriptions", "PlanVersionQuota")

    for entry in _PLANS:
        plan = Plan.objects.using(db).create(
            code=entry["code"],
            name=entry["name"],
            is_public=True,
            trial_days=0,
            grace_period_days=3,
            is_default_trial=False,
        )
        version = PlanVersion.objects.using(db).create(
            plan=plan,
            version_number=1,
            price_monthly=entry["price_monthly"],
            price_yearly=entry["price_yearly"],
            currency=_CURRENCY,
            is_current=True,
        )
        PlanVersionQuota.objects.using(db).bulk_create(
            PlanVersionQuota(plan_version=version, quota_key=key, limit=limit)
            for key, limit in entry["quotas"].items()
        )
        PlanVersionFeature.objects.using(db).bulk_create(
            PlanVersionFeature(plan_version=version, feature_key=key, enabled=enabled)
            for key, enabled in entry["features"].items()
        )


def _unseed(apps, schema_editor):
    db = schema_editor.connection.alias
    Plan = apps.get_model("subscriptions", "Plan")
    Plan.objects.using(db).filter(code__in=[e["code"] for e in _PLANS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0003_subscriptioncheckoutsession"),
    ]

    operations = [
        migrations.RunPython(_seed, _unseed),
    ]
