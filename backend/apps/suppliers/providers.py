"""
`SupplierProvider` ABC + `MockSupplier` -- docs/ARCHITECTURE.md section
10's "v1: interfaces + models + MockSupplier only" boundary. Only the
methods this phase actually calls are declared: `fetch_catalog`.
`fetch_inventory`/`fetch_prices` (section 10's full sketch) and
`place_order`/`track_order` are deliberately NOT declared here --
nothing in this phase implements or calls them, and an abstract method
with zero implementations/callers is exactly the kind of half-finished
surface this project avoids. Add them when a real provider (or the
deferred purchase-order workflow) actually needs them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class SupplierProductDTO:
    external_id: str
    name: str
    cost_amount: int
    currency: str
    stock: int


class SupplierProvider(ABC):
    @abstractmethod
    def fetch_catalog(self) -> Iterator[SupplierProductDTO]: ...


class MockSupplier(SupplierProvider):
    """Deterministic fake catalog -- same shape every call (so a repeat
    sync is idempotent and demoable), no network/credentials of any
    kind."""

    _CATALOG: tuple[tuple[str, str, int, int], ...] = (
        ("MOCK-001", "Wireless Mouse", 1200, 50),
        ("MOCK-002", "Mechanical Keyboard", 4500, 20),
        ("MOCK-003", "USB-C Hub", 2200, 35),
        ("MOCK-004", "Laptop Stand", 3100, 15),
        ("MOCK-005", "Webcam 1080p", 5600, 10),
    )

    def fetch_catalog(self) -> Iterator[SupplierProductDTO]:
        for external_id, name, cost_amount, stock in self._CATALOG:
            yield SupplierProductDTO(
                external_id=external_id,
                name=name,
                cost_amount=cost_amount,
                currency="SAR",
                stock=stock,
            )


_PROVIDERS: dict[str, type[SupplierProvider]] = {"mock": MockSupplier}


def get_provider(provider_key: str) -> SupplierProvider:
    try:
        return _PROVIDERS[provider_key]()
    except KeyError as exc:
        raise ValueError(f"Unknown supplier provider_key: {provider_key!r}") from exc
