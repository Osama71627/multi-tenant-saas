"""
Dashboard surface for Products & Catalog, under
`/api/v1/dashboard/stores/<uuid:store_id>/...` -- every view here
subclasses `StoreScopedAPIView` (apps/stores/mixins.py), which resolves
`self.store` from the URL path (never the Host header) and 403/404s
before any handler runs. See that class's docstring for the 404-vs-403
reasoning this whole surface relies on.

Product/variant lookups below rely on RLS (via `TenantManager`, already
scoped to `self.store` by `TenantMiddleware`) to make a cross-tenant id
simply not exist from this connection's point of view -- a `DoesNotExist`
for "wrong store" and "genuinely no such row" look identical from here,
which is exactly the point (apps/tenancy/models.py).
"""

from __future__ import annotations

from django.db import IntegrityError, models, transaction
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.catalog import services
from apps.catalog.models import (
    Category,
    Product,
    ProductOption,
    ProductOptionValue,
    ProductVariant,
    Tag,
)
from apps.catalog.serializers import (
    AddOptionSerializer,
    AddOptionValueSerializer,
    CategorySerializer,
    CreateProductSerializer,
    CreateVariantSerializer,
    ProductOptionSerializer,
    ProductOptionValueSerializer,
    ProductSerializer,
    ProductVariantSerializer,
    StorefrontCategorySerializer,
    StorefrontProductDetailSerializer,
    StorefrontProductListSerializer,
    TagSerializer,
    UpdateProductSerializer,
)
from apps.catalog.services import DuplicateOptionSelectionError, LastVariantError
from apps.stores.mixins import StorefrontAPIView, StoreScopedAPIView
from apps.subscriptions.entitlements import QuotaExceededError


def _get_product_or_404(product_id) -> Product:
    try:
        return Product.objects.get(id=product_id)
    except (Product.DoesNotExist, ValueError, TypeError) as exc:
        raise Http404 from exc


def _get_option_or_404(product: Product, option_id) -> ProductOption:
    try:
        return ProductOption.objects.get(id=option_id, product=product)
    except (ProductOption.DoesNotExist, ValueError, TypeError) as exc:
        raise Http404 from exc


def _get_variant_or_404(product: Product, variant_id) -> ProductVariant:
    try:
        return ProductVariant.objects.get(id=variant_id, product=product)
    except (ProductVariant.DoesNotExist, ValueError, TypeError) as exc:
        raise Http404 from exc


class ProductListCreateView(StoreScopedAPIView):
    @extend_schema(responses=ProductSerializer(many=True))
    def get(self, request: Request, store_id) -> Response:
        products = Product.objects.all()
        status_filter = request.query_params.get("status")
        if status_filter:
            products = products.filter(status=status_filter)
        return Response(ProductSerializer(products, many=True).data)

    @extend_schema(request=CreateProductSerializer, responses={201: ProductSerializer})
    def post(self, request: Request, store_id) -> Response:
        serializer = CreateProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            product = services.create_product(store=self.store, **serializer.validated_data)
        except IntegrityError:
            return Response(
                {"detail": "A product with this slug or SKU already exists in this store."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except QuotaExceededError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_402_PAYMENT_REQUIRED)
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


class ProductDetailView(StoreScopedAPIView):
    @extend_schema(responses=ProductSerializer)
    def get(self, request: Request, store_id, product_id) -> Response:
        return Response(ProductSerializer(_get_product_or_404(product_id)).data)

    @extend_schema(request=UpdateProductSerializer, responses={200: ProductSerializer})
    def patch(self, request: Request, store_id, product_id) -> Response:
        product = _get_product_or_404(product_id)
        serializer = UpdateProductSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data.get("status")
        try:
            with transaction.atomic(using="default"):
                if new_status is not None:
                    services.check_quota_for_status_change(
                        store=self.store, current_status=product.status, new_status=new_status
                    )
                serializer.save()
        except IntegrityError:
            return Response(
                {"detail": "A product with this slug already exists in this store."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except QuotaExceededError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_402_PAYMENT_REQUIRED)
        return Response(ProductSerializer(product).data)

    def delete(self, request: Request, store_id, product_id) -> Response:
        _get_product_or_404(product_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductOptionListCreateView(StoreScopedAPIView):
    def post(self, request: Request, store_id, product_id) -> Response:
        product = _get_product_or_404(product_id)
        serializer = AddOptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            option = services.add_option(
                store=self.store, product=product, **serializer.validated_data
            )
        except IntegrityError:
            return Response(
                {"detail": "This product already has an option with this name."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ProductOptionSerializer(option).data, status=status.HTTP_201_CREATED)


class ProductOptionValueListCreateView(StoreScopedAPIView):
    def post(self, request: Request, store_id, product_id, option_id) -> Response:
        product = _get_product_or_404(product_id)
        option = _get_option_or_404(product, option_id)
        serializer = AddOptionValueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            value = services.add_option_value(
                store=self.store, option=option, **serializer.validated_data
            )
        except IntegrityError:
            return Response(
                {"detail": "This option already has this value."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ProductOptionValueSerializer(value).data, status=status.HTTP_201_CREATED)


class ProductVariantListCreateView(StoreScopedAPIView):
    def post(self, request: Request, store_id, product_id) -> Response:
        product = _get_product_or_404(product_id)
        serializer = CreateVariantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            variant = services.create_variant(
                store=self.store, product=product, **serializer.validated_data
            )
        except (DuplicateOptionSelectionError, ProductOptionValue.DoesNotExist) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            return Response(
                {
                    "detail": "This SKU is already used, or this exact combination of "
                    "options already exists for this product."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ProductVariantSerializer(variant).data, status=status.HTTP_201_CREATED)


class ProductVariantDetailView(StoreScopedAPIView):
    def delete(self, request: Request, store_id, product_id, variant_id) -> Response:
        product = _get_product_or_404(product_id)
        variant = _get_variant_or_404(product, variant_id)
        try:
            services.delete_variant(product=product, variant=variant)
        except LastVariantError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryListCreateView(StoreScopedAPIView):
    def get(self, request: Request, store_id) -> Response:
        return Response(CategorySerializer(Category.objects.all(), many=True).data)

    def post(self, request: Request, store_id) -> Response:
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(store=self.store)
        except IntegrityError:
            return Response(
                {"detail": "A category with this slug already exists in this store."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TagListCreateView(StoreScopedAPIView):
    def get(self, request: Request, store_id) -> Response:
        return Response(TagSerializer(Tag.objects.all(), many=True).data)

    def post(self, request: Request, store_id) -> Response:
        serializer = TagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(store=self.store)
        except IntegrityError:
            return Response(
                {"detail": "A tag with this slug already exists in this store."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# --------------------------------------------------------------------------
# Storefront (customer-facing, Host-resolved) catalog browsing -- Phase
# 13. `StorefrontAPIView` (apps/stores/mixins.py), not `StoreScopedAPIView`
# -- guest-accessible, tenant resolved from the Host header, never the
# URL path. Every queryset below is hard-filtered to `status="active"` --
# a draft/archived product or variant must never be reachable here, even
# by guessing its id/slug.
# --------------------------------------------------------------------------


_SORT_OPTIONS = {"name", "newest", "price_asc", "price_desc"}


class StorefrontProductListView(StorefrontAPIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                "category", str, required=False, description="Filter by category slug."
            ),
            OpenApiParameter(
                "sort",
                str,
                required=False,
                description="One of name (default), newest, price_asc, price_desc.",
            ),
        ],
        responses=StorefrontProductListSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        products = Product.objects.filter(status=Product.Status.ACTIVE).prefetch_related(
            models.Prefetch(
                "variants",
                queryset=ProductVariant.objects.filter(
                    status=ProductVariant.Status.ACTIVE
                ).order_by("position", "id"),
            )
        )

        category_slug = request.query_params.get("category")
        if category_slug:
            products = products.filter(product_categories__category__slug=category_slug)

        # `.filter(variants__status=...)`, not `.exclude(variants__isnull=True)` --
        # a product can have variants that are ALL archived, which must not
        # show up here (no purchasable variant left). Joins on the real
        # status column, independent of the prefetch above.
        products = products.filter(variants__status=ProductVariant.Status.ACTIVE).distinct()

        # Real gap found live: the storefront's own product listing page
        # had no sort at all -- always the same fixed name order, no way
        # for a shopper to browse by price or by what's new. Price lives
        # on ProductVariant, not Product, so price sort needs an
        # annotation (the cheapest active variant's price, matching what
        # StorefrontProductListSerializer.price_amount itself shows --
        # "the first active variant by position" -- close enough for a
        # sort order without a second, more complex "lowest price"
        # semantic that would disagree with the price actually displayed
        # on each card).
        sort = request.query_params.get("sort", "name")
        if sort not in _SORT_OPTIONS:
            sort = "name"
        if sort == "newest":
            products = products.order_by("-created_at", "id")
        elif sort in ("price_asc", "price_desc"):
            products = products.annotate(_sort_price=models.Min("variants__price_amount"))
            products = products.order_by(
                "_sort_price" if sort == "price_asc" else "-_sort_price", "id"
            )
        else:
            products = products.order_by("name", "id")

        return Response(StorefrontProductListSerializer(products, many=True).data)


class StorefrontProductDetailView(StorefrontAPIView):
    @extend_schema(responses=StorefrontProductDetailSerializer)
    def get(self, request: Request, slug: str) -> Response:
        try:
            product = (
                Product.objects.filter(status=Product.Status.ACTIVE)
                .prefetch_related(
                    "options__values",
                    models.Prefetch(
                        "variants",
                        queryset=ProductVariant.objects.filter(status=ProductVariant.Status.ACTIVE)
                        .order_by("position", "id")
                        .prefetch_related("option_values__option", "option_values__option_value"),
                    ),
                )
                .get(slug=slug)
            )
        except (Product.DoesNotExist, ValueError, TypeError) as exc:
            raise Http404 from exc
        if not product.variants.all():
            # Every variant is archived -- nothing purchasable, so this
            # page must not be reachable (same "not found" as a genuinely
            # nonexistent product, not a 200 with an empty variants list).
            raise Http404
        return Response(StorefrontProductDetailSerializer(product).data)


class StorefrontCategoryListView(StorefrontAPIView):
    @extend_schema(responses=StorefrontCategorySerializer(many=True))
    def get(self, request: Request) -> Response:
        categories = Category.objects.order_by("position", "id")
        return Response(StorefrontCategorySerializer(categories, many=True).data)
