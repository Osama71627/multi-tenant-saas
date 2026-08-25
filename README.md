# Multi-Tenant SaaS E-Commerce Platform

Status: **Phase 6 complete** (Cart & Pricing). See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design,
[docs/DECISIONS.md](docs/DECISIONS.md) for the approved architectural
decisions, and the phase reports for what was actually built and
verified in each phase: [Phase 1](docs/PHASE_1_REPORT.md) (Bootstrap +
Core + Tenancy), [Phase 2](docs/PHASE_2_REPORT.md) (Accounts & Auth),
[Phase 3](docs/PHASE_3_REPORT.md) (Store Creation),
[Phase 4](docs/PHASE_4_REPORT.md) (Products & Catalog),
[Phase 5](docs/PHASE_5_REPORT.md) (Inventory),
[Phase 6](docs/PHASE_6_REPORT.md) (Cart & Pricing).

## Stack

- **Backend:** Python 3.12, Django 5.2 LTS, Django REST Framework, PostgreSQL 18, Redis, Celery
- **Frontend:** Next.js 15 (App Router), React 19, TypeScript -- lands starting Phase 12
- **Infra:** Docker Compose (dev), Nginx/Caddy + Gunicorn (production)

## Multi-tenancy in one paragraph

Every store is a row in `stores_store`; every tenant-owned table carries
a `store_id` and is protected by PostgreSQL Row-Level Security. The
application connects as a restricted `app_user` role that structurally
**cannot** bypass RLS (no superuser, no BYPASSRLS, doesn't own the
tables) -- so isolation holds even if application code has a bug. See
[docs/ARCHITECTURE.md section 2](docs/ARCHITECTURE.md#2-multi-tenant-strategy--most-important-decision-in-the-project).

## Running locally

### Option A -- Docker Compose (the officially supported path)

```bash
cp .env.example .env
docker compose up --build
```

Backend: http://localhost:8000 · API docs: http://localhost:8000/api/docs/

> This has been authored to the same standard as the rest of Phase 1 but
> has **not been executed** in the environment this was built in (no
> Docker Desktop installed there) -- see docs/PHASE_1_REPORT.md for
> exactly what was verified instead (a local PostgreSQL 18 + Redis via
> WSL2). Please confirm `docker compose up --build` works cleanly on your
> machine and report back anything that doesn't.

### Option B -- run Postgres/Redis yourself, backend natively

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
```

You need a PostgreSQL 18 database and **two roles** (see
[docs/ARCHITECTURE.md section 2.3](docs/ARCHITECTURE.md)):

```sql
CREATE ROLE app_migrator LOGIN PASSWORD 'devpass_migrator' CREATEDB;
CREATE ROLE app_user LOGIN PASSWORD 'devpass_appuser'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE DATABASE saas_dev OWNER app_migrator;
\c saas_dev
GRANT CONNECT ON DATABASE saas_dev TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO app_user;
```

(`infra/postgres/init/01-roles.sh` does exactly this automatically when
using Docker Compose.)

```bash
cp .env.example .env        # adjust DATABASE_URL/MIGRATOR_DATABASE_URL/REDIS_URL if needed
python manage.py migrate --database=migrator
python manage.py createsuperuser
python manage.py runserver
```

**Note:** migrations run ONLY via `--database=migrator`. Plain
`python manage.py migrate` is a deliberate no-op -- see
`apps/tenancy/routers.py`.

## Running tests

```bash
cd backend
pytest                                          # full suite
pytest tests/test_tenant_isolation.py -v        # the tenant-isolation suite specifically
pytest --cov=apps --cov-report=term-missing     # with coverage
```

## Quality gates (all run in CI, see .github/workflows/ci.yml)

```bash
ruff check .
black --check .
lint-imports --config pyproject.toml
bandit -q -r apps config -x "*/tests/*,*/migrations/*"
mypy apps config
python manage.py makemigrations --check --dry-run
pytest --cov=apps --cov-fail-under=80
```

## Project layout

```
backend/           Django project (config/ + apps/*)
frontend/           Next.js monorepo -- starts Phase 12
docs/                Architecture, decisions, phase reports
infra/postgres/init/ Docker-compose Postgres role bootstrap
.github/workflows/   CI
```

## Documentation index

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) -- full system design (18 sections)
- [docs/DECISIONS.md](docs/DECISIONS.md) -- the 8 approved architectural decisions + open questions
- [docs/PHASE_1_REPORT.md](docs/PHASE_1_REPORT.md) -- Phase 1 completion report
