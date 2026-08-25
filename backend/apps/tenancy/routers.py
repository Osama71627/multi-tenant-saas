class MigratorRouter:
    """
    Schema changes may ONLY run against the `migrator` database alias
    (the `app_migrator` role, which owns the schema). The `default` alias
    (`app_user`) is the restricted, RLS-bound connection the running
    application uses for all business queries and must never run DDL.

    Practical effect: plain `python manage.py migrate` (which defaults to
    the `default` alias) becomes a clean no-op instead of a confusing
    permission-denied error, making the required `--database=migrator`
    an explicit, impossible-to-forget-silently step. See
    docs/ARCHITECTURE.md section 2.3, layer 4.
    """

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == "migrator"
