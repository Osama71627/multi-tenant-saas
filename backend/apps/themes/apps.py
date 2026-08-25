from django.apps import AppConfig


class ThemesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.themes"
    label = "themes"

    def ready(self) -> None:
        from apps.stores import hooks
        from apps.themes import services

        def _provision_store_theme(store, *, theme_preset_id=None, **kwargs) -> None:
            try:
                services.provision_store_theme(store=store, theme_preset_id=theme_preset_id)
            except services.ThemePresetNotFoundError as exc:
                raise hooks.PostCreationHookError(str(exc)) from exc
            # NoDefaultThemePresetError is deliberately NOT caught here --
            # a missing seeded default is a deployment/seed-data gap, not
            # a client error; it should surface as a 500, not a 400.

        hooks.register_post_creation_hook(_provision_store_theme)
