from django.apps import AppConfig
from django.db.models.signals import post_migrate


class TenancyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenancy"
    label = "tenancy"

    def ready(self):
        from apps.tenancy.privileges import grant_app_user_privileges

        # Idempotent: safe to run after every app's migrations, not just
        # once. Only actually executes when the `migrator` alias was the
        # one migrated (see the `using` guard inside the function) --
        # that's the role that owns newly-created tables, so it's the
        # only one that can grant on them.
        post_migrate.connect(
            grant_app_user_privileges,
            dispatch_uid="tenancy_grant_app_user_privileges",
        )
