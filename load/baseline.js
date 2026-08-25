// Phase 18 -- docs/ARCHITECTURE.md section 14's "Load" row: k6 (marked
// optional in that doc), a BASELINE measurement on the catalog and
// checkout paths, not a full load-testing suite. Deliberately minimal:
// catalog list + detail (the two real hot GET paths a storefront visitor
// hits on every page load) and checkout/start (the first, lightest
// write on the purchase path -- a full purchase-through-payment run
// under load needs a per-VU cart/address/shipping sequence that adds a
// lot of scripting weight for a "baseline", not a proportionate amount
// of signal for this phase's scope).
//
// Run against a REAL store hostname (tenant resolution is Host-header-
// based, apps/stores/middleware.py -- there is no tenant-less baseline
// to measure against). Point BASE_URL/PRODUCT_SLUG at any real, already-
// seeded store+product (e.g. the `make seed` data, or any store created
// through the dashboard) -- never run this against a shared/production
// store without the merchant's explicit knowledge, per this project's
// own security posture on load-testing shared infrastructure.
//
//   k6 run -e BASE_URL=http://<store-slug>.lvh.me:8000 -e PRODUCT_SLUG=<slug> load/baseline.js
//
// No thresholds/pass-fail gate is asserted here on purpose -- this is a
// baseline measurement to read and record, not a CI quality gate (the
// architecture doc doesn't ask for one, and a load-based CI gate is
// exactly the kind of infrastructure this phase's Fast-MVP scope
// shouldn't invent unasked).

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    catalog_baseline: {
      executor: "ramping-vus",
      exec: "catalog",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 20 },
        { duration: "1m", target: 20 },
        { duration: "15s", target: 0 },
      ],
    },
    checkout_start_baseline: {
      executor: "ramping-vus",
      exec: "checkoutStart",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 10 },
        { duration: "1m", target: 10 },
        { duration: "15s", target: 0 },
      ],
    },
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const PRODUCT_SLUG = __ENV.PRODUCT_SLUG || "";

export function catalog() {
  const listRes = http.get(`${BASE_URL}/api/v1/storefront/products`);
  check(listRes, { "catalog list: 200": (r) => r.status === 200 });

  if (PRODUCT_SLUG) {
    const detailRes = http.get(`${BASE_URL}/api/v1/storefront/products/${PRODUCT_SLUG}`);
    check(detailRes, { "catalog detail: 200": (r) => r.status === 200 });
  }

  sleep(1);
}

export function checkoutStart() {
  const res = http.post(`${BASE_URL}/api/v1/storefront/checkout/start`, null, {
    headers: { "content-type": "application/json" },
  });
  check(res, { "checkout/start: 2xx or 4xx (empty cart is a valid baseline hit)": (r) => r.status < 500 });
  sleep(1);
}
