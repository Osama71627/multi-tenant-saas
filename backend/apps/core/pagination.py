from rest_framework.pagination import CursorPagination, PageNumberPagination


class DefaultPageNumberPagination(PageNumberPagination):
    """Used by dashboard/platform surfaces -- merchants expect page numbers."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class StorefrontCursorPagination(CursorPagination):
    """
    Used by storefront listing endpoints (product catalog, etc.) -- cursor
    pagination avoids the "page drifts as new products are added" problem
    and scales to large catalogs without COUNT(*) on every request.
    """

    page_size = 24
    max_page_size = 96
    ordering = "-created_at"
