"""
Regression test for a real infrastructure bug found in Phase 4 (see
docs/PHASE_4_REPORT.md and backend/conftest.py:django_db_setup):
pytest-django only creates a test database for the aliases referenced by
a test's `django_db` marker. Every test in this project uses the bare
`pytest.mark.django_db` (no explicit `databases=[...]`), which resolves
to just `{"default"}` -- "migrator" was never included, so "default"
(configured as `TEST: {"MIRROR": "migrator"}`, config/settings/test.py)
had nothing to mirror and silently fell back to its literal configured
NAME: the REAL DEV DATABASE, not an isolated test one. Every test's
writes went to the actual dev database the whole time, invisible because
pytest-django's automatic transaction rollback happened to make ordinary
tests look safe anyway.

`conftest.py` fixes this by overriding `django_db_setup` to force both
aliases into `setup_databases()` regardless of what any marker declares.
This test exists so that fix can never silently regress.
"""

import pytest
from django.db import connections

pytestmark = pytest.mark.django_db


def test_default_and_migrator_aliases_point_at_an_isolated_test_database():
    default_name = connections["default"].settings_dict["NAME"]
    migrator_name = connections["migrator"].settings_dict["NAME"]

    # `settings.DATABASES[...]['NAME']` isn't a safe comparison baseline
    # here: Django's own test setup mutates that dict in place too, so by
    # the time a test runs it already reads "test_..." as well. The
    # `test_` prefix (Django's own convention for a database it created
    # for testing, config/settings/test.py's `TEST: {"NAME": ...}`) is
    # the real, direct signal that this is NOT the literal dev database.
    assert default_name.startswith("test_"), (
        f"'default' DB alias is '{default_name}', not a test database -- "
        "django_db_setup in conftest.py isn't overriding pytest-django's "
        "alias auto-detection correctly"
    )
    assert default_name == migrator_name, (
        "'default' should MIRROR 'migrator' during tests -- they must be "
        "the same physical database"
    )
