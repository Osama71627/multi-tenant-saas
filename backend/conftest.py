"""
Project-wide pytest fixtures.

`django_db` (via pytest-django) resets *database* state between tests
(transaction rollback), but does NOT touch Django's cache -- and
TenantMiddleware caches hostname -> store_id lookups there (see
apps/tenancy/middleware.py). Without this, two tests that happen to reuse
the same hostname string (plausible: tests read like documentation, e.g.
"store-a.lvh.me") can leak a stale, already-rolled-back store id from one
test into the next and produce a confusing false negative. Real symptom
we hit while building this: a later test saw `store: null` for a host it
had just correctly registered, because an earlier test's cache entry
(now pointing at a deleted row) was still within its TTL.
"""

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_django_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(scope="session")
def django_db_setup(request, django_db_blocker):
    """
    Overrides pytest-django's own `django_db_setup` fixture (same name,
    session-scoped -- a fixture defined here wins over the plugin's).

    Real bug found in Phase 4 (docs/PHASE_4_REPORT.md): pytest-django
    only creates a test database for the ALIASES referenced by a test's
    `django_db` marker, and every test in this project uses the bare
    `pytest.mark.django_db` (no explicit `databases=[...]`), which
    resolves to just `{"default"}` -- "migrator" was NEVER included.
    Since "default" is configured as `TEST: {"MIRROR": "migrator"}"
    (config/settings/test.py) and "migrator" was never set up either,
    Django's `setup_databases()` had nothing to mirror and silently fell
    back to "default"'s literal configured NAME -- the REAL DEV DATABASE
    ("saas_dev"), not "test_saas_dev". Every test's writes went to the
    real dev database the whole time; only pytest-django's automatic
    transaction rollback (unrelated to this bug) made that look safe for
    ordinary tests. Confirmed directly: `connections["default"
    ].settings_dict["NAME"]` printed "saas_dev" inside a running test,
    and a stray committed row from an earlier debugging session was
    found sitting in the actual "saas_dev" database.

    Fix: force BOTH aliases into `setup_databases()` explicitly,
    regardless of what any individual test's marker declares -- the
    officially-documented pytest-django pattern for "an extra database
    alias that always needs to exist" (their own docs cite exactly this
    read-replica/mirror scenario, which is what config/settings/test.py
    already described itself as using).
    """
    from django.db import connections
    from django.test.utils import setup_databases, teardown_databases

    # Captured BEFORE setup_databases() touches anything -- this is the
    # literal dev-database name from settings, un-mutated.
    configured_names = {
        alias: connections[alias].settings_dict["NAME"]
        for alias in ("default", "migrator", "platform")
    }

    with django_db_blocker.unblock():
        db_cfg = setup_databases(
            verbosity=request.config.option.verbose,
            interactive=False,
            aliases=["default", "migrator", "platform"],
        )

    # The automatic guard the Phase 4 bug should have had from day one
    # (docs/PHASE_4_REPORT.md section 5.1): don't just trust that this
    # override + config/settings/test.py's MIRROR setup worked --
    # verify it, hard, before a single test gets to run. If isolation
    # is ever broken again (a settings refactor, someone "simplifying"
    # this fixture), the whole session aborts here with a clear error
    # instead of quietly testing against -- and mutating -- real dev
    # data again.
    for alias in ("default", "migrator", "platform"):
        runtime_name = connections[alias].settings_dict["NAME"]
        assert runtime_name != configured_names[alias], (
            f"DB alias '{alias}' is still pointing at its configured dev-database "
            f"name ({runtime_name!r}) after test DB setup -- test isolation is "
            "broken, refusing to run any test against it. See "
            "docs/PHASE_4_REPORT.md section 5.1 and backend/tests/test_db_isolation.py."
        )
        assert runtime_name.startswith("test_"), runtime_name

    yield
    with django_db_blocker.unblock():
        # "default" uses CONN_MAX_AGE=60 (persistent connections,
        # config/settings/base.py) -- its connection can still be open
        # from the last test when we get here, which makes `DROP
        # DATABASE` fail ("being accessed by other users"). Close
        # everything explicitly before tearing down.
        connections.close_all()
        teardown_databases(db_cfg, verbosity=request.config.option.verbose)
