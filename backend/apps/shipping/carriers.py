"""
Provider abstraction for `carrier_calculated` shipping methods --
mirrors the same pattern the architecture reserves for `PaymentProvider`/
`SupplierProvider` (docs/ARCHITECTURE.md sections 12/10): an ABC now,
real carrier integrations (SMSA/Aramex/DHL) later, with zero rewrite of
callers when they land. v1 ships only `MockCarrier` -- a deterministic
stand-in, not a placeholder that returns fake success; its rates are
real, computed, testable numbers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CarrierRateOption:
    service_name: str
    price_amount: int
    currency: str


class CarrierProvider(ABC):
    @abstractmethod
    def get_rates(
        self, *, country_code: str, region: str, weight_grams: int, currency: str
    ) -> list[CarrierRateOption]:
        """Real implementations will call an external carrier API here."""

    @abstractmethod
    def create_shipment(self, **kwargs) -> str:
        """Returns a tracking number. Real implementation lands with apps.orders (Phase 8+)."""

    @abstractmethod
    def track(self, tracking_number: str) -> list[dict]:
        """Returns a list of tracking events. Real implementation lands with
        apps.orders (Phase 8+)."""

    @abstractmethod
    def cancel(self, tracking_number: str) -> None:
        """Real implementation lands with apps.orders (Phase 8+)."""


class MockCarrier(CarrierProvider):
    """
    Deterministic weight-tiered pricing -- real math, not a stub. Exists
    so `carrier_calculated` methods are genuinely exercisable end-to-end
    in v1 without a live external API dependency.
    """

    _BASE_PRICE_AMOUNT = 1500  # minor units
    _PRICE_PER_KG = 300

    def get_rates(
        self, *, country_code: str, region: str, weight_grams: int, currency: str
    ) -> list[CarrierRateOption]:
        weight_kg_ceil = -(-max(weight_grams, 0) // 1000)  # ceil division, no float
        price = self._BASE_PRICE_AMOUNT + weight_kg_ceil * self._PRICE_PER_KG
        return [
            CarrierRateOption(service_name="Mock Standard", price_amount=price, currency=currency)
        ]

    def create_shipment(self, **kwargs) -> str:
        raise NotImplementedError("Shipment creation lands with apps.orders (Phase 8+).")

    def track(self, tracking_number: str) -> list[dict]:
        raise NotImplementedError("Tracking lands with apps.orders (Phase 8+).")

    def cancel(self, tracking_number: str) -> None:
        raise NotImplementedError("Cancellation lands with apps.orders (Phase 8+).")
