from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"
    label = "catalog"

    def ready(self) -> None:
        from apps.catalog.models import Product
        from apps.subscriptions.entitlements import register_live_counter

        def _count_non_archived_products(store) -> int:
            # `.objects` (not `.unscoped`): this always runs with tenant
            # context already set to `store` by whatever service function
            # called `entitlements.check_quota` -- not a cross-tenant read.
            return Product.objects.exclude(status=Product.Status.ARCHIVED).count()

        register_live_counter("products", _count_non_archived_products)
