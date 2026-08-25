from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self) -> None:
        # Forces Celery's lazy `autodiscover_tasks()` (config/celery.py) to
        # actually run now, once Django's app registry is fully populated --
        # see that module's comment for why this can't happen at plain
        # import time, and why it's needed at all (apps.core.events looks
        # tasks up by string name via the Celery app's own registry, which
        # is otherwise only ever populated inside a real worker process).
        from config.celery import app as celery_app

        celery_app.autodiscover_tasks(force=True)
