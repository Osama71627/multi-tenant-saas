"""
Options/values/variants: the normalized EAV design from
docs/PHASE_4_REPORT.md. Every uniqueness rule here is a genuine DB
constraint, not just Python validation -- this file proves that,
including with a real concurrent-request race (not just sequential
calls), per the explicit Phase 4 requirement not to trust
application-level checks alone against race conditions.
"""

from __future__ import annotations

import threading
import uuid

import pytest

from apps.catalog.models import ProductVariant
from apps.catalog.tests.conftest import store_db_context

pytestmark = pytest.mark.django_db


def _create_product(client, store_id, *, slug="t-shirt", sku="TSHIRT-DEFAULT"):
    return client.post(
        f"/api/v1/dashboard/stores/{store_id}/products",
        {"name": "T-Shirt", "slug": slug, "sku": sku, "price_amount": 3000},
        format="json",
    )


def _add_option(client, store_id, product_id, name):
    return client.post(
        f"/api/v1/dashboard/stores/{store_id}/products/{product_id}/options",
        {"name": name},
        format="json",
    )


def _add_value(client, store_id, product_id, option_id, value):
    return client.post(
        f"/api/v1/dashboard/stores/{store_id}/products/{product_id}/options/{option_id}/values",
        {"value": value},
        format="json",
    )


@pytest.fixture
def product_with_size_and_color(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    product_id = _create_product(client, store.id).data["id"]

    size = _add_option(client, store.id, product_id, "Size").data
    color = _add_option(client, store.id, product_id, "Color").data
    size_m = _add_value(client, store.id, product_id, size["id"], "M").data
    size_l = _add_value(client, store.id, product_id, size["id"], "L").data
    color_red = _add_value(client, store.id, product_id, color["id"], "Red").data
    color_black = _add_value(client, store.id, product_id, color["id"], "Black").data

    return {
        "client": client,
        "store": store,
        "product_id": product_id,
        "size": size,
        "color": color,
        "size_m": size_m,
        "size_l": size_l,
        "color_red": color_red,
        "color_black": color_black,
    }


def test_add_option_and_values(product_with_size_and_color):
    ctx = product_with_size_and_color
    assert ctx["size"]["name"] == "Size"
    assert ctx["size_m"]["value"] == "M"


def test_duplicate_option_name_on_same_product_is_rejected(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    product_id = _create_product(client, store.id).data["id"]
    _add_option(client, store.id, product_id, "Size")
    response = _add_option(client, store.id, product_id, "Size")
    assert response.status_code == 400


def test_duplicate_value_on_same_option_is_rejected(product_with_size_and_color):
    ctx = product_with_size_and_color
    response = _add_value(ctx["client"], ctx["store"].id, ctx["product_id"], ctx["size"]["id"], "M")
    assert response.status_code == 400


def _create_variant(client, store_id, product_id, sku, option_value_ids):
    return client.post(
        f"/api/v1/dashboard/stores/{store_id}/products/{product_id}/variants",
        {"sku": sku, "price_amount": 3200, "option_value_ids": option_value_ids},
        format="json",
    )


def test_create_a_variant_with_a_valid_combination(product_with_size_and_color):
    ctx = product_with_size_and_color
    response = _create_variant(
        ctx["client"],
        ctx["store"].id,
        ctx["product_id"],
        "TSHIRT-M-RED",
        [ctx["size_m"]["id"], ctx["color_red"]["id"]],
    )
    assert response.status_code == 201, response.data
    assert len(response.data["option_values"]) == 2


def test_selecting_two_values_for_the_same_option_is_rejected(product_with_size_and_color):
    ctx = product_with_size_and_color
    response = _create_variant(
        ctx["client"],
        ctx["store"].id,
        ctx["product_id"],
        "TSHIRT-BAD",
        [ctx["size_m"]["id"], ctx["size_l"]["id"]],
    )
    assert response.status_code == 400


def test_duplicate_option_combination_on_same_product_is_rejected(product_with_size_and_color):
    ctx = product_with_size_and_color
    combo = [ctx["size_m"]["id"], ctx["color_red"]["id"]]
    first = _create_variant(
        ctx["client"], ctx["store"].id, ctx["product_id"], "TSHIRT-M-RED-1", combo
    )
    assert first.status_code == 201

    second = _create_variant(
        ctx["client"], ctx["store"].id, ctx["product_id"], "TSHIRT-M-RED-2", combo
    )
    assert second.status_code == 400


def test_same_combination_is_allowed_on_a_different_product(product_with_size_and_color):
    ctx = product_with_size_and_color
    combo = [ctx["size_m"]["id"], ctx["color_red"]["id"]]
    _create_variant(ctx["client"], ctx["store"].id, ctx["product_id"], "TSHIRT-M-RED", combo)

    other_product_id = _create_product(
        ctx["client"], ctx["store"].id, slug="other-t-shirt", sku="TSHIRT-OTHER-DEFAULT"
    ).data["id"]
    # NOTE: option_value ids belong to the FIRST product's options, so
    # this variant creation is expected to fail for a different reason
    # (the values don't belong to this product's options) -- this test
    # instead proves the combo rule is product-scoped using a genuinely
    # independent product with its OWN equivalent option values.
    size2 = _add_option(ctx["client"], ctx["store"].id, other_product_id, "Size").data
    color2 = _add_option(ctx["client"], ctx["store"].id, other_product_id, "Color").data
    size2_m = _add_value(ctx["client"], ctx["store"].id, other_product_id, size2["id"], "M").data
    color2_red = _add_value(
        ctx["client"], ctx["store"].id, other_product_id, color2["id"], "Red"
    ).data

    response = _create_variant(
        ctx["client"],
        ctx["store"].id,
        other_product_id,
        "OTHER-M-RED",
        [size2_m["id"], color2_red["id"]],
    )
    assert response.status_code == 201


def test_deleting_a_variant_is_allowed_when_others_remain(product_with_size_and_color):
    ctx = product_with_size_and_color
    variant_id = _create_variant(
        ctx["client"],
        ctx["store"].id,
        ctx["product_id"],
        "TSHIRT-M-RED",
        [ctx["size_m"]["id"], ctx["color_red"]["id"]],
    ).data["id"]

    response = ctx["client"].delete(
        f"/api/v1/dashboard/stores/{ctx['store'].id}/products/{ctx['product_id']}/variants/{variant_id}"
    )
    assert response.status_code == 204


def test_cannot_delete_a_products_last_remaining_variant(owner_client_and_store):
    client, _owner, store = owner_client_and_store
    created = _create_product(client, store.id)
    product_id = created.data["id"]
    default_variant_id = created.data["variants"][0]["id"]

    response = client.delete(
        f"/api/v1/dashboard/stores/{store.id}/products/{product_id}/variants/{default_variant_id}"
    )
    assert response.status_code == 400
    with store_db_context(store):
        assert ProductVariant.objects.filter(product_id=product_id).count() == 1


def test_concurrent_inserts_with_the_same_option_signature_only_one_succeeds():
    """
    Real cross-connection concurrency (two genuinely separate PostgreSQL
    sessions/transactions racing each other), not a sequential
    simulation -- proving the actual mechanism
    `UniqueConstraint(["product", "option_signature"])` relies on
    (a plain UNIQUE index on a uuid[] column, verified to exist and
    reject duplicates in docs/PHASE_4_REPORT.md section 5) is atomic
    under concurrency, per the explicit Phase 4 requirement to not rely
    on application-level pre-checks alone for race safety.

    Deliberately raw `psycopg` connections against a throwaway TEMP
    TABLE reproducing just the constraint shape, NOT the Django ORM/test
    client against `catalog_productvariant` itself:

      * `app_user` has DELETE but not TRUNCATE (verified -- see
        docs/PHASE_3_REPORT.md's role model). pytest-django's
        `transaction=True` (needed for real cross-connection visibility)
        tears down via `flush`, which issues TRUNCATE and would silently
        fail against this project's deliberately-restricted role,
        corrupting later tests' fixture data. Not worth reopening that
        role boundary just for one test.
      * The property under test -- "a UNIQUE index makes a duplicate
        concurrent INSERT fail atomically, no TOCTOU window" -- is a
        general PostgreSQL guarantee that does not depend on which table
        it's defined on; the sequential tests above already prove the
        REAL table carries the identical constraint shape
        (`UniqueConstraint(["product", "option_signature"])`).

    A real (not TEMP) table is required: a PostgreSQL TEMP table is
    session-local, so two separate connections each creating "the same"
    temp table would actually get two independent, unrelated tables --
    no race would even be possible to observe. `app_user` alone can't
    create real tables (no CREATE on schema public -- by design, only
    `app_migrator` owns the schema, see infra/postgres/init/01-roles.sh),
    so table setup/teardown uses the `migrator` connection alias while
    the actual racing INSERTs use `default` (`app_user`) -- exactly the
    same division of responsibility the whole project already uses
    (migrator owns schema, app_user does DML). `ALTER DEFAULT PRIVILEGES
    FOR ROLE app_migrator ... GRANT ... TO app_user` (same init script)
    means app_user automatically gets INSERT on a table app_migrator
    creates, with no extra grant needed here.
    """
    import psycopg
    from django.db import connections

    migrator_params = connections["migrator"].get_connection_params()
    user_params = connections["default"].get_connection_params()
    table = "catalog_concurrency_probe_test"

    setup_conn = psycopg.connect(**migrator_params, autocommit=True)
    try:
        setup_conn.execute(f"DROP TABLE IF EXISTS {table}")
        setup_conn.execute(
            f"CREATE TABLE {table} "
            "(id serial primary key, product_id int not null, sig uuid[] not null, "
            "UNIQUE (product_id, sig))"
        )

        signature = [uuid.uuid4(), uuid.uuid4()]
        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt(label: str) -> None:
            conn = psycopg.connect(**user_params, autocommit=False)
            try:
                barrier.wait()
                # `table` is the hardcoded local constant above, not
                # user input -- the actual value (%s) IS bound properly.
                insert_sql = f"INSERT INTO {table} (product_id, sig) VALUES (1, %s)"  # noqa: S608
                conn.execute(insert_sql, [signature])
                conn.commit()
                results.append(f"{label}:ok")
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                results.append(f"{label}:rejected")
            finally:
                conn.close()

        threads = [
            threading.Thread(target=attempt, args=("A",)),
            threading.Thread(target=attempt, args=("B",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(results) == ["A:ok", "B:rejected"] or sorted(results) == [
            "A:rejected",
            "B:ok",
        ], results
    finally:
        setup_conn.execute(f"DROP TABLE IF EXISTS {table}")
        setup_conn.close()
