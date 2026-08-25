"""
Structured JSON logging with mandatory secret redaction.

Per docs/DECISIONS.md governance point 18: passwords, JWTs, refresh
tokens, card data, and payment secrets must NEVER reach a log line, even
by accident (e.g. someone does `logger.info("login attempt", **request.data)`
without thinking). The redaction filter is defense-in-depth: engineers
should still avoid logging raw payloads, but if they forget, this catches
the common cases before anything leaves the process.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

_REDACTED = "***REDACTED***"

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|passwd|secret|token|authorization|api[_-]?key|"
    r"card[_-]?number|cvv|cvc|refresh|access[_-]?token|private[_-]?key)",
    re.IGNORECASE,
)

# Catches bearer tokens / JWTs embedded directly in free-text messages,
# e.g. an accidentally-logged `Authorization: Bearer eyJ...` header.
_JWT_LIKE_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")
_BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._-]+\b", re.IGNORECASE)


def _redact_value(key: str, value: Any) -> Any:
    if isinstance(value, dict):
        return _redact_mapping(value)
    if isinstance(value, list | tuple):
        return [_redact_value(key, v) for v in value]
    if _SENSITIVE_KEY_PATTERN.search(key):
        return _REDACTED
    if isinstance(value, str):
        value = _JWT_LIKE_PATTERN.sub(_REDACTED, value)
        value = _BEARER_PATTERN.sub(f"Bearer {_REDACTED}", value)
    return value


def _redact_mapping(mapping: dict) -> dict:
    return {k: _redact_value(k, v) for k, v in mapping.items()}


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _JWT_LIKE_PATTERN.sub(_REDACTED, record.msg)
            record.msg = _BEARER_PATTERN.sub(f"Bearer {_REDACTED}", record.msg)
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            record.extra = _redact_mapping(extra)
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, default=str)
