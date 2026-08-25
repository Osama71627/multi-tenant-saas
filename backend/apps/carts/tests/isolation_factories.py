"""Registers apps.carts TenantOwnedModels with the generic isolation test suite."""

from apps.carts.models import Cart, CartItem
from apps.catalog.models import Product, ProductVariant
from apps.core.tokens import generate_raw_token, hash_raw_token
from apps.tenancy.testing import register


def _make_cart(store, suffix: str) -> Cart:
    return Cart.objects.create(
        store=store, token_hash=hash_raw_token(f"{generate_raw_token()}-{suffix}"), currency="SAR"
    )


def _make_variant(store, suffix: str) -> ProductVariant:
    product = Product.objects.create(
        store=store, name=f"Product {suffix}", slug=f"product-{store.slug}-{suffix}"
    )
    return ProductVariant.objects.create(
        store=store,
        product=product,
        sku=f"SKU-{store.slug}-{suffix}",
        currency="SAR",
        price_amount=1000,
        is_default=True,
        option_signature=[],
    )


@register(Cart)
def _cart_factory(store, suffix: str) -> Cart:
    return _make_cart(store, suffix)


@register(CartItem)
def _cart_item_factory(store, suffix: str) -> CartItem:
    cart = _make_cart(store, suffix)
    variant = _make_variant(store, suffix)
    return CartItem.objects.create(
        store=store, cart=cart, variant=variant, quantity=1, unit_price_amount=1000, currency="SAR"
    )
