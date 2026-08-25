"""Provider registry -- adding a new provider is one new module + one entry here.
`apps.payments.services` never imports a concrete provider class directly."""

from __future__ import annotations

from apps.payments.providers.base import PaymentProvider
from apps.payments.providers.manual_cod import ManualCodProvider
from apps.payments.providers.mock import MockProvider
from apps.payments.providers.stripe_provider import StripeProvider

PROVIDER_KEYS = ("mock", "manual_cod", "stripe")


def get_provider(*, provider_key: str, secret_key: str = "") -> PaymentProvider:
    if provider_key == "mock":
        return MockProvider()
    if provider_key == "manual_cod":
        return ManualCodProvider()
    if provider_key == "stripe":
        if not secret_key:
            raise ValueError("the stripe provider requires a decrypted secret_key")
        return StripeProvider(secret_key=secret_key)
    raise ValueError(f"unknown provider_key: {provider_key!r}")
