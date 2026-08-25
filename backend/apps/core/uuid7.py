"""
Dependency-free, RFC 9562 compliant UUIDv7 generator.

Why this exists instead of `uuid.uuid7()` (stdlib) or a PyPI package:
see docs/DECISIONS.md ("UUIDv7 resolution"). Summary: `uuid.uuid7()` only
exists starting Python 3.14, which is not the runtime this project pins
(Python 3.12, chosen for ecosystem maturity of psycopg/Pillow/celery
wheels). PostgreSQL's native `uuidv7()` only exists from Postgres 18 and
we don't want primary-key generation coupled to a specific DB major
version. Third-party PyPI implementations are an unnecessary dependency
for ~40 lines of well-specified, easily-tested logic. So: we own it.

Layout (128 bits, RFC 9562 section 5.7):

    bits 127..80 (48)  unix_ts_ms
    bits  79..76 ( 4)  version      = 0b0111
    bits  75..64 (12)  rand_a       (used here as a monotonic counter,
                                      "Method 1: Fixed-Length Dedicated
                                      Counter" in RFC 9562 section 6.2)
    bits  63..62 ( 2)  variant      = 0b10
    bits  61.. 0 (62)  rand_b       (cryptographically random)

Monotonicity: within the same millisecond, `rand_a` increments instead of
being re-randomized, so UUIDs generated back-to-back in a hot loop remain
sortable -- this is what gives UUIDv7 its B-tree-index-locality advantage
over UUIDv4. On the rare 12-bit counter overflow (4096 IDs in the same
millisecond) the timestamp is bumped forward by one ms rather than ever
going backward or colliding.
"""

from __future__ import annotations

import secrets
import threading
import time
import uuid

_VERSION = 0x7
_VARIANT = 0b10
_COUNTER_BITS = 12
_COUNTER_MASK = (1 << _COUNTER_BITS) - 1
_RAND_B_BITS = 62
_RAND_B_MASK = (1 << _RAND_B_BITS) - 1

_lock = threading.Lock()
_last_ts_ms = 0
_last_counter = 0


def _next_ts_and_counter() -> tuple[int, int]:
    """Thread-safe monotonic (timestamp_ms, counter) pair."""
    global _last_ts_ms, _last_counter
    with _lock:
        ts_ms = time.time_ns() // 1_000_000
        if ts_ms <= _last_ts_ms:
            # Clock didn't advance (same ms, or -- rarely -- went backward,
            # e.g. NTP adjustment). Never emit a UUID that sorts before the
            # last one: hold the timestamp and advance the counter.
            ts_ms = _last_ts_ms
            _last_counter = (_last_counter + 1) & _COUNTER_MASK
            if _last_counter == 0:
                # Counter exhausted (4096 IDs within one ms): force the
                # clock forward by 1ms rather than reusing rand_a=0, which
                # would risk a same-(ts,counter) collision.
                ts_ms += 1
                _last_ts_ms = ts_ms
        else:
            _last_ts_ms = ts_ms
            _last_counter = secrets.randbits(_COUNTER_BITS)
        return ts_ms, _last_counter


def uuid7() -> uuid.UUID:
    """Generate one RFC 9562 UUIDv7."""
    ts_ms, counter = _next_ts_and_counter()
    rand_b = secrets.randbits(_RAND_B_BITS)

    value = (ts_ms & 0xFFFFFFFFFFFF) << 80
    value |= _VERSION << 76
    value |= (counter & _COUNTER_MASK) << 64
    value |= _VARIANT << 62
    value |= rand_b & _RAND_B_MASK

    return uuid.UUID(int=value)


def uuid7_timestamp_ms(value: uuid.UUID) -> int:
    """Extract the embedded millisecond timestamp back out. Test/debug use."""
    return value.int >> 80


def is_uuid7(value: uuid.UUID) -> bool:
    """True if `value` has the UUIDv7 version and RFC 4122 variant bits set."""
    return value.version == 7 and (value.int >> 62) & 0b11 == _VARIANT
