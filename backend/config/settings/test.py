"""
Test settings.

The tricky bit: we need Django's test runner to CREATE and MIGRATE an
ephemeral test database (which requires CREATEDB -- only `app_migrator`
has that), while our tenant-isolation tests must run their queries as the
genuinely-restricted `app_user` role so the proof is real, not simulated.

Solution (a documented Django pattern, normally used for read-replica
testing): make `migrator` the "real" test database -- Django creates and
migrates it. Make `default` a MIRROR of `migrator` -- Django does NOT try
to create a separate database for it, it just points the `default`
connection (which still authenticates as `app_user`) at the same physical
test database. Every plain `Model.objects...` call in a test therefore
goes through the actual restricted role.
"""

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-any-real-use"  # noqa: S105 # nosec B105

# Real CI failure found on the first actual GitHub Actions run: this used
# to hardcode "test_saas_dev" as a literal -- it only ever "worked"
# because the local dev database also happens to be named "saas_dev", so
# it coincidentally matched Django's own default test-name convention
# ("test_" + NAME). CI's database is "saas_ci" (MIGRATOR_DATABASE_URL),
# so the literal diverged from what "default"/"platform" (which have no
# explicit TEST.NAME override, so Django auto-derives "test_saas_ci" for
# them) resolved to -- three aliases that were supposed to share ONE
# physical test database ended up with three different signatures,
# and Django's own dependency-ordering raised "Circular dependency in
# TEST[DEPENDENCIES]" trying to reconcile the mismatch. Deriving it from
# the actual configured NAME (whatever environment this runs in) instead
# of a literal makes this portable and removes the coincidence.
DATABASES["migrator"]["TEST"] = {"NAME": f"test_{DATABASES['migrator']['NAME']}"}  # noqa: F405
DATABASES["default"]["TEST"] = {"MIRROR": "migrator"}  # noqa: F405
# Same MIRROR trick for the Phase 14 platform alias: same physical test
# database, but the connection still authenticates as the genuinely
# BYPASSRLS-but-narrowly-granted `app_platform_admin` role, so
# apps.platform_admin tests prove real privilege behavior, not simulated.
DATABASES["platform"]["TEST"] = {"MIRROR": "migrator"}  # noqa: F405

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast, tests only

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
