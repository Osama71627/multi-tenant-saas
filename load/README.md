# Load baseline (k6)

docs/ARCHITECTURE.md section 14 marks k6 **optional** and scopes it to a
baseline measurement on the catalog and checkout paths — this is that
baseline, not a full load-testing suite or a CI gate.

## Running

Point it at any real, already-seeded store (tenant resolution is
Host-header-based, so there's no tenant-less target to run this against):

```bash
k6 run -e BASE_URL=http://<store-slug>.lvh.me:8000 -e PRODUCT_SLUG=<slug> load/baseline.js
```

Verified locally against a real seeded store: 3848 requests over ~1m45s,
100% of the script's own checks passing, p95 ≈ 95ms. Re-run and record a
fresh number before treating any past run as current — this is a
snapshot, not a maintained benchmark.

Never run this against a shared/production store without the merchant's
explicit knowledge.
