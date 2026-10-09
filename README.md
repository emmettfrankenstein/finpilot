# FinPilot

Investment portfolio and goal monitoring console for an internal wealth-service team.
Built for the FinPilot full-stack assignment with **React + TypeScript**, **Django REST Framework**
and **PostgreSQL 16**. All data is synthetic.

| Component | Local URL |
|---|---|
| Web app (Docker, nginx) | http://localhost:8080 |
| Web app (dev server) | http://localhost:5173 |
| API base | http://localhost:8000/api/v1 |
| Swagger UI | http://localhost:8000/api/v1/docs |
| ReDoc | http://localhost:8000/api/v1/redoc |
| OpenAPI schema (YAML) | http://localhost:8000/api/v1/schema |
| Health (readiness / liveness) | `/api/v1/health`, `/api/v1/health/live` |

Supporting documents:

- [`docs/FinPilot_Architecture_Report.pdf`](docs/FinPilot_Architecture_Report.pdf): architecture and design report (source: [`docs/architecture.md`](docs/architecture.md))
- [`DECISIONS.md`](DECISIONS.md): assumptions, data-quality handling, deliberate omissions, known limitations
- [`docs/sql/reviewer_queries.sql`](docs/sql/reviewer_queries.sql): the six reviewer SQL tasks, plus [`EXPLAIN (ANALYZE, BUFFERS)` output](docs/sql/explain_transactions_listing.txt)

## Quick start (Docker, one command)

Requires Docker with Compose v2.

```bash
cp .env.example .env        # then edit the passwords and secret key
docker compose up --build
```

On start the API container waits for PostgreSQL, applies migrations, loads the CSVs in `data/`
through the import pipeline and creates the demo users. Restarts are safe: files already loaded
are skipped. Open http://localhost:8080.

### Demo credentials

The demo users are created from environment variables, so no password is committed:

| Username | Role | Password comes from |
|---|---|---|
| `viewer` | VIEWER: customers, portfolio, transactions, goals | `DEMO_VIEWER_PASSWORD` in `.env` |
| `admin` | ADMIN: everything above plus data imports | `DEMO_ADMIN_PASSWORD` in `.env` |

With the unchanged `.env.example` values these are `change-me-viewer` and `change-me-admin`.
Change them before sharing a running instance.

## Local development without Docker

Requires Python 3.12+, Node 22+ and a PostgreSQL 16 server.

```bash
# 1. Database (any local PostgreSQL; pg_trgm is a trusted extension the owner can create)
createuser finpilot --pwprompt --createdb      # CREATEDB lets pytest create its test database
createdb finpilot --owner finpilot

# 2. API
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
set -a; source ../.env; set +a                 # POSTGRES_*, DJANGO_*, DEMO_* variables
export DJANGO_DEBUG=true                       # local only: plain HTTP, readable errors
python manage.py migrate
python manage.py seed_data --data-dir ../data
python manage.py create_demo_users
python manage.py runserver 8000

# 3. Web (second terminal)
cd frontend
npm ci
npm run dev                                    # http://localhost:5173, proxies /api to :8000
```

### Tests, lint and build

```bash
cd backend && pytest && ruff check . && ruff format --check .
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

Backend tests run against a real PostgreSQL database (pytest-django creates `test_finpilot`):
41 tests cover every supplied data anomaly, the duplicate policy, auth and roles, portfolio
aggregation, transaction filters and goal validation. Frontend tests (Vitest + Testing Library)
cover the API client's token refresh, goal form validation and table rendering.

## Environment variables

See [`.env.example`](.env.example). The important ones:

| Variable | Purpose |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | Database connection |
| `DJANGO_SECRET_KEY` | Required when `DJANGO_DEBUG=false`; also signs JWTs unless `JWT_SIGNING_KEY` is set |
| `DJANGO_DEBUG` | `true` only for local development |
| `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | Host and origin allow-lists |
| `REFRESH_COOKIE_SECURE` | `false` only for plain-HTTP localhost; `true` behind TLS |
| `JWT_ACCESS_MINUTES`, `JWT_REFRESH_HOURS` | Token lifetimes (default 15 minutes / 8 hours) |
| `LOG_LEVEL`, `LOG_FORMAT` | `json` (default) or `plain` logs |
| `DEMO_VIEWER_PASSWORD`, `DEMO_ADMIN_PASSWORD` | Demo user passwords |
| `SEED_ON_START` | Docker only: seed CSVs and demo users on start (default `true`) |

## Database migrations

- `python manage.py migrate` builds the schema from an empty database, including the `pg_trgm`
  extension, constraints, indexes, the reporting views (`v_latest_price`, `v_position_valuation`,
  `v_monthly_net_flows`) and the goal id sequence.
- In Docker, migrations run in the API entrypoint before gunicorn starts. PostgreSQL has
  transactional DDL and Django wraps each migration in a transaction, so a failing migration is
  rolled back and the container exits non-zero instead of serving a half-migrated schema.
  `/api/v1/health` reports pending migrations as not ready.
- Roll back with `python manage.py migrate portfolio <previous_migration>`. Every custom SQL
  migration ships reverse SQL.

## Importing data

- Seed or re-seed: `python manage.py seed_data --data-dir ../data` (idempotent).
- Admin UI: sign in as `admin` and open **Data imports**.
- API: `POST /api/v1/admin/imports/transactions` with a multipart `file` field (ADMIN only).
  The response contains row counts and the rejected rows with reasons. Re-sending the same file
  returns `409 Conflict`. The same endpoint accepts every supplied dataset name.

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"change-me-admin"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access"])')
curl -s -X POST localhost:8000/api/v1/admin/imports/transactions \
  -H "Authorization: Bearer $TOKEN" -F file=@data/transactions.csv
```

## Project layout

```
backend/
  config/            settings (env-driven), URLs
  apps/core/         request-id middleware, JSON logging, error envelope, health, pagination
  apps/users/        custom user with VIEWER/ADMIN role, JWT login/refresh/logout
  apps/portfolio/    domain models, SQL views, portfolio service, API views
  apps/ingestion/    CSV parsers, per-dataset validation specs, staging + merge pipeline
  tests/             pytest suite (PostgreSQL)
frontend/
  src/api/           typed fetch client (token refresh), TanStack Query hooks, types
  src/auth/          auth context and route guard
  src/components/    tables, chart, pagination, goal form, states
  src/pages/         login, customers, customer overview/positions/transactions/goals, imports
data/                supplied CSVs, unmodified
docs/                architecture report, SQL tasks, EXPLAIN output
.github/workflows/   CI
```

## CI/CD

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push to `main` and every
pull request:

1. **Backend**: ruff lint and format check, migration completeness check, migrate a clean
   PostgreSQL service container, strict OpenAPI validation, seed twice (idempotency), pytest.
2. **Frontend**: ESLint (zero warnings), TypeScript check, Vitest, production build.
3. **Security**: `pip-audit` and `npm audit` for known-vulnerable dependencies.
4. **Docker**: builds both images and smoke-tests the full Compose stack through nginx.

Any failing step fails the pipeline. The deployment step is local: `docker compose up --build`
on the target machine. The architecture report describes how this maps to a cloud deployment.
