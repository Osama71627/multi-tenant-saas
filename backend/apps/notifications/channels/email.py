"""
The only concrete Channel implemented in Phase 11. Reuses Django's own
`send_mail` -- the SAME mechanism `apps.accounts.services` already uses
for email verification/password reset (console/locmem backend in
dev/test, SMTP in production, config/settings/production.py) -- no new
email-sending primitive invented alongside an existing one.
"""

from __future__ import annotations

from django.core.mail import send_mail

from apps.notifications.channels.base import NotificationChannel, PermanentSendError


class EmailChannel(NotificationChannel):
    def send(self, *, recipient: str, subject: str, body: str) -> None:
        if not recipient:
            raise PermanentSendError("No recipient email address.")
        # `fail_silently=False` (the default) -- any backend failure raises,
        # which the caller (apps.notifications.services) classifies as
        # transient unless it's one of the PermanentSendError cases above.
        send_mail(subject=subject, message=body, from_email=None, recipient_list=[recipient])
