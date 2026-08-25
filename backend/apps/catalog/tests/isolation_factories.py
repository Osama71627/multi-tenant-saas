"""
Registers every apps.catalog TenantOwnedModel with the generic isolation
test suite (backend/tests/test_tenant_isolation.py). See
apps/stores/tests/isolation_factories.py for the pattern.

Each factory is self-contained (creates whatever parent rows it needs)
and is called with the tenant context already active for `store` -- it
must never wrap tenant_context() itself, matching every other
isolation_factories.py in the project.
"""

from apps.catalog.models import (
    Category,
    Product,
    ProductCategory,
    ProductImage,
    ProductOption,
    ProductOptionValue,
    ProductTag,
    ProductVariant,
    Tag,
    VariantOptionValue,
)
from apps.tenancy.testing import register


def _make_product(store, suffix: str) -> Product:
    return Product.objects.create(
        store=store, name=f"Product {suffix}", slug=f"product-{store.slug}-{suffix}"
    )


def _make_option(store, product: Product, suffix: str) -> ProductOption:
    return ProductOption.objects.create(store=store, product=product, name=f"Option {suffix}")


def _make_option_value(store, option: ProductOption, suffix: str) -> ProductOptionValue:
    return ProductOptionValue.objects.create(store=store, option=option, value=f"Value {suffix}")


def _make_variant(store, product: Product, suffix: str, *, option_signature=None) -> ProductVariant:
    return ProductVariant.objects.create(
        store=store,
        product=product,
        sku=f"SKU-{store.slug}-{suffix}",
        currency="SAR",
        price_amount=1000,
        option_signature=option_signature or [],
    )


@register(Product)
def _product_factory(store, suffix: str) -> Product:
    return _make_product(store, suffix)


@register(ProductOption)
def _option_factory(store, suffix: str) -> ProductOption:
    return _make_option(store, _make_product(store, suffix), suffix)


@register(ProductOptionValue)
def _option_value_factory(store, suffix: str) -> ProductOptionValue:
    option = _make_option(store, _make_product(store, suffix), suffix)
    return _make_option_value(store, option, suffix)


@register(ProductVariant)
def _variant_factory(store, suffix: str) -> ProductVariant:
    return _make_variant(store, _make_product(store, suffix), suffix)


@register(VariantOptionValue)
def _variant_option_value_factory(store, suffix: str) -> VariantOptionValue:
    product = _make_product(store, suffix)
    option = _make_option(store, product, suffix)
    option_value = _make_option_value(store, option, suffix)
    variant = _make_variant(store, product, suffix, option_signature=[option_value.id])
    return VariantOptionValue.objects.create(
        store=store, variant=variant, option=option, option_value=option_value
    )


@register(Category)
def _category_factory(store, suffix: str) -> Category:
    return Category.objects.create(
        store=store, name=f"Category {suffix}", slug=f"category-{store.slug}-{suffix}"
    )


@register(ProductCategory)
def _product_category_factory(store, suffix: str) -> ProductCategory:
    product = _make_product(store, suffix)
    category = Category.objects.create(
        store=store, name=f"Category {suffix}", slug=f"category-{store.slug}-{suffix}"
    )
    return ProductCategory.objects.create(store=store, product=product, category=category)


@register(Tag)
def _tag_factory(store, suffix: str) -> Tag:
    return Tag.objects.create(store=store, name=f"Tag {suffix}", slug=f"tag-{store.slug}-{suffix}")


@register(ProductTag)
def _product_tag_factory(store, suffix: str) -> ProductTag:
    product = _make_product(store, suffix)
    tag = Tag.objects.create(store=store, name=f"Tag {suffix}", slug=f"tag-{store.slug}-{suffix}")
    return ProductTag.objects.create(store=store, product=product, tag=tag)


@register(ProductImage)
def _product_image_factory(store, suffix: str) -> ProductImage:
    product = _make_product(store, suffix)
    return ProductImage.objects.create(
        store=store, product=product, url=f"https://example.com/{store.slug}-{suffix}.jpg"
    )
