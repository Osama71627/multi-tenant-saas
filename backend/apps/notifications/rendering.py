"""
Safe template rendering -- approved review-round requirement: even
platform-global templates must not use arbitrary Python/Jinja execution.
`string.Template` (stdlib) is used deliberately: `$name`-style flat
substitution has NO attribute/method/item access syntax at all, so a
template body structurally cannot reach into a model, call a function,
or traverse anything beyond the exact keys the caller puts in `context`
-- there is nothing resembling Jinja's `{{ order.customer.delete }}`
expression language to exploit in the first place.

The context dict itself is built by a Service/selector (below), never
passed a model instance -- only plain strings.
"""

from __future__ import annotations

from string import Template

from apps.notifications.models import NotificationTemplate


def render_template(*, template: NotificationTemplate, context: dict[str, str]) -> tuple[str, str]:
    """`safe_substitute` (not `substitute`): a context key the template
    doesn't use is simply ignored, and a placeholder with no matching
    context key is left as literal text rather than raising -- correct
    for a locked-down global template where a typo must not become a
    500 in a Celery task."""
    subject = Template(template.subject).safe_substitute(context)
    body = Template(template.body_text).safe_substitute(context)
    return subject, body


def build_order_confirmation_context(*, order, store) -> dict[str, str]:
    """`order`/`store` are read for their plain field values ONLY, right
    here -- nothing beyond this flat dict is ever handed to the renderer."""
    return {
        "order_number": order.number,
        "order_email": order.email,
        "order_total": f"{order.total_amount / 100:.2f} {order.currency}",
        "store_name": store.name,
    }
