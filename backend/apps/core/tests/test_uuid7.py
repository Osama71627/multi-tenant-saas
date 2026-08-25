import threading
import time

from apps.core.uuid7 import is_uuid7, uuid7, uuid7_timestamp_ms


def test_version_and_variant_bits_are_correct():
    value = uuid7()
    assert value.version == 7
    assert is_uuid7(value)


def test_timestamp_roundtrips_to_roughly_now():
    before = int(time.time() * 1000)
    value = uuid7()
    after = int(time.time() * 1000)
    embedded = uuid7_timestamp_ms(value)
    assert before <= embedded <= after


def test_sequential_calls_are_unique():
    values = {uuid7() for _ in range(20_000)}
    assert len(values) == 20_000


def test_sequential_calls_are_monotonically_non_decreasing():
    values = [uuid7() for _ in range(20_000)]
    assert values == sorted(values), "UUIDv7 must sort in generation order"


def test_thread_safety_no_collisions_across_threads():
    results: list[set] = [set() for _ in range(8)]

    def worker(bucket: set) -> None:
        for _ in range(5_000):
            bucket.add(uuid7())

    threads = [threading.Thread(target=worker, args=(results[i],)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    all_values = set().union(*results)
    assert len(all_values) == 8 * 5_000, "concurrent generation must never collide"
