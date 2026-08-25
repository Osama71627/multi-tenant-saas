"""
Business logic for product/variant/option management. Kept out of
views per docs/ARCHITECTURE.md section 11 -- the invariants here
(option-signature uniqueness, "a product always has >=1 variant") are
exactly the kind of thing that must not live in a View.
"""

from __future__ import annotations

from django.db import transaction

from apps.catalog.models import (
    Product,
    ProductOption,
    ProductOptionValue,
    ProductVariant,
    VariantOptionValue,
)
from apps.stores.models import Store
from apps.subscriptions import entitlements


class DuplicateOptionSelectionError(Exception):
    """Two selected option values belong to the same ProductOption (e.g. Size=M and Size=L)."""


class LastVariantError(Exception):
    """A Product must always have at least one variant -- Phase 4 architecture rule 1/7."""


def create_product(
    *,
    store: Store,
    name: str,
    slug: str,
    sku: str,
    price_amount: int,
    currency: str | None = None,
    description: str = "",
    seo_title: str = "",
    seo_description: str = "",
    cost_price_amount: int | None = None,
) -> Product:
    """
    Creates a `Product` with exactly one variant: `is_default=True`,
    `option_signature=[]`. This is the ONLY way a Product should come
    into existence -- there is no "product with zero variants" state,
    ever, even transiently outside this one transaction.

    `cost_price_amount` (Phase 16, apps.suppliers): the same field
    `create_variant` already exposes for additional variants, just
    threaded through for the default one too -- lets a supplier import
    record its cost on the variant it creates, no separate write path.
    """
    currency = currency or store.default_currency
    with transaction.atomic(using="default"):
        # A newly created Product is `draft` (never `archived`), so this is
        # always a usage-increasing mutation for the "products" quota --
        # approved architecture decision 6, checked+locked inside this same
        # transaction as the row it guards.
        entitlements.check_quota(store=store, quota_key="products")
        product = Product.objects.create(
            store=store,
            name=name,
            slug=slug,
            description=description,
            seo_title=seo_title,
            seo_description=seo_description,
        )
        ProductVariant.objects.create(
            store=store,
            product=product,
            sku=sku,
            currency=currency,
            price_amount=price_amount,
            cost_price_amount=cost_price_amount,
            is_default=True,
            option_signature=[],
        )
    return product


def check_quota_for_status_change(*, store: Store, current_status: str, new_status: str) -> None:
    """
    Must be called inside the SAME `transaction.atomic()` as the actual
    status-changing save (apps/catalog/views.py's PATCH handler) -- Phase
    10, approved architecture decision 6: quota enforcement must cover
    every mutation that increases the live "products" count, not just
    `create_product`. Un-archiving (`archived` -> anything else)
    increases it exactly like creation; archiving decreases it and is
    always allowed (an operation that doesn't increase usage must never
    be blocked just because the store is already over its limit);
    draft<->active is lateral, no count change either way.
    """
    if current_status == Product.Status.ARCHIVED and new_status != Product.Status.ARCHIVED:
        entitlements.check_quota(store=store, quota_key="products")


def add_option(*, store: Store, product: Product, name: str) -> ProductOption:
    next_position = ProductOption.objects.filter(
        product=product
    ).count()  # small N per product; simplicity over a MAX() query
    return ProductOption.objects.create(
        store=store, product=product, name=name, position=next_position
    )


def add_option_value(*, store: Store, option: ProductOption, value: str) -> ProductOptionValue:
    next_position = ProductOptionValue.objects.filter(option=option).count()
    return ProductOptionValue.objects.create(
        store=store, option=option, value=value, position=next_position
    )


def create_variant(
    *,
    store: Store,
    product: Product,
    sku: str,
    price_amount: int,
    option_value_ids: list,
    currency: str | None = None,
    compare_at_price_amount: int | None = None,
    cost_price_amount: int | None = None,
) -> ProductVariant:
    """
    Creates an additional variant for a specific combination of option
    values. Both DB-level guarantees this relies on (verified, not
    assumed -- see apps/catalog/models.py's module docstring):

      * `option_signature` (sorted option_value ids) + a
        `UniqueConstraint(["product", "option_signature"])` rejects a
        duplicate combination for this product, atomically, even under
        concurrent requests -- no read-then-write race window.
      * `VariantOptionValue`'s `UniqueConstraint(["variant", "option"])`
        rejects two values for the same option on one variant.

    The `seen_options` check below is a fast, friendly pre-check for the
    common case (e.g. a client accidentally sending Size=M and Size=L
    together) -- NOT the actual security/integrity boundary; that's the
    DB constraints above, which still apply even if this check were
    removed or buggy.
    """
    currency = currency or store.default_currency
    with transaction.atomic(using="default"):
        option_values = list(
            ProductOptionValue.objects.select_related("option").filter(id__in=option_value_ids)
        )
        if len(option_values) != len(set(option_value_ids)):
            raise ProductOptionValue.DoesNotExist(
                "one or more option_value_ids do not exist in this store"
            )

        seen_options: set = set()
        for option_value in option_values:
            if option_value.option_id in seen_options:
                raise DuplicateOptionSelectionError(
                    f"multiple values selected for option {option_value.option_id}"
                )
            seen_options.add(option_value.option_id)

        variant = ProductVariant.objects.create(
            store=store,
            product=product,
            sku=sku,
            currency=currency,
            price_amount=price_amount,
            compare_at_price_amount=compare_at_price_amount,
            cost_price_amount=cost_price_amount,
            is_default=False,
            option_signature=sorted(ov.id for ov in option_values),
        )
        VariantOptionValue.objects.bulk_create(
            [
                VariantOptionValue(
                    store=store,
                    variant=variant,
                    option=option_value.option,
                    option_value=option_value,
                )
                for option_value in option_values
            ]
        )
    return variant


def delete_variant(*, product: Product, variant: ProductVariant) -> None:
    """
    Refuses to delete a product's last remaining variant -- Phase 4 rule
    1: every Product has >=1 variant, always. `select_for_update()`
    locks the product's variant rows for the duration of this
    transaction, closing the check-then-delete race between two
    concurrent "delete a different variant" requests that could
    otherwise both see ">=1 remaining" and both proceed, leaving zero.
    """
    with transaction.atomic(using="default"):
        locked_variant_ids = list(
            ProductVariant.objects.select_for_update()
            .filter(product=product)
            .values_list("id", flat=True)
        )
        if locked_variant_ids == [variant.id]:
            raise LastVariantError("cannot delete a product's last remaining variant")
        variant.delete()
