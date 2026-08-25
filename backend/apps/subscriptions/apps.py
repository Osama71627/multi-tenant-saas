from django.apps import AppConfig


class SubscriptionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.subscriptions"
    label = "subscriptions"

    def ready(self) -> None:
        from apps.stores import hooks
        from apps.subscriptions import entitlements, services

        def _provision_trial_subscription(store, **kwargs) -> None:
            services.provision_trial_subscription(store=store)

        hooks.register_post_creation_hook(_provision_trial_subscription)

        def _write_gate(store) -> None:
            try:
                entitlements.require_active_store(store=store)
            except entitlements.StoreNotPurchasableError as exc:
                raise hooks.WriteBlockedError(str(exc)) from exc

        hooks.register_write_gate(_write_gate)
