import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("saas")
# `config_from_object(..., namespace="CELERY")` already loads
# `CELERY_TASK_ROUTES` from settings (config/settings/base.py) as
# `app.conf.task_routes` -- queue assignment lives there, in ONE place,
# not duplicated here. (Phase 11 fix: this file previously ALSO set
# `app.conf.task_routes` directly, silently overwriting whatever
# `config_from_object` had just loaded from settings -- a real,
# pre-existing duplicate-source-of-truth bug, found while wiring this
# phase's own queue routing. `apps.suppliers.tasks.*` -> "sync" is
# preserved in settings' CELERY_TASK_ROUTES even though apps.suppliers
# doesn't exist yet, same forward-looking placeholder this file already
# had.)
app.config_from_object("django.conf:settings", namespace="CELERY")
# Lazy (default `force=False`): actual `apps.<x>.tasks` imports are
# deferred until something triggers them -- normally Celery's own
# `import_modules` signal, which fires when a REAL worker process boots.
# It never fires in a Django request-serving or test process that never
# starts an actual worker, which left every app's task registry silently
# EMPTY outside a real worker for the whole project (latent since
# Phase 0/1 -- unnoticed because every task so far was invoked either as
# a plain Python function call in tests, or via
# `dispatch_for_store`/`.delay()` on an already-imported task object,
# neither of which needs the app's `tasks` registry populated). Phase 11
# is the first thing that looks a task up by STRING NAME via
# `app.tasks[name]` (apps/core/events.py, so apps.core never imports a
# domain app) and found this gap directly.
#
# Fix: `apps.core.apps.CoreConfig.ready()` (runs once Django's app
# registry is fully populated -- calling `force=True` here directly,
# at THIS module's import time, fails with `AppRegistryNotReady`, since
# this module is imported as part of `config/__init__.py`, itself
# imported while Django is still constructing `django.conf.settings`)
# explicitly forces discovery at the correct, later point in startup.
app.autodiscover_tasks()
