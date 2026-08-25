from django.apps import AppConfig
from django.db.models.signals import post_migrate


class PlatformAdminConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.platform_admin"
    label = "platform_admin"

    def ready(self) -> None:
        from apps.platform_admin.privileges import grant_platform_admin_privileges

        post_migrate.connect(
            grant_platform_admin_privileges,
            dispatch_uid="platform_admin_grant_privileges",
        )
