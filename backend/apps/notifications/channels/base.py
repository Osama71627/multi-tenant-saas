"""
Channel abstraction -- deliberately small (approved review-round scope:
"لا تبنِ الآن SMS/WhatsApp/Push... Channel abstraction يجب أن تبقى صغيرة
ولا تتحول إلى provider framework ضخم استباقي"). Same ABC shape as
`apps.payments.providers.base.PaymentProvider`/
`apps.shipping.carriers.CarrierProvider`, with exactly ONE concrete
implementation (`EmailChannel`) for Phase 11 -- structure exists for a
future SMS/WhatsApp/push channel, none is built now.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class PermanentSendError(Exception):
    """The send can never succeed no matter how many times it's retried
    (e.g. a structurally invalid recipient) -- distinct from any other
    exception, which the caller treats as transient/retryable."""


class NotificationChannel(ABC):
    @abstractmethod
    def send(self, *, recipient: str, subject: str, body: str) -> None:
        """Raises `PermanentSendError` for a non-retryable failure, or any
        other exception for a transient one the caller should retry."""
