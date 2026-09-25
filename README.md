# Alma Leads

Public lead-intake form (name, email, resume) with confirmation + attorney notification emails, and an
authenticated dashboard where attorneys review leads, download resumes, and mark leads as reached out.

Design: [`../docs/system-design.md`](../docs/system-design.md). Implementation notes and deviations: [`NOTES.md`](NOTES.md).

| Piece | Stack |
|---|---|
| `apps/api` | FastAPI · SQLAlchemy 2 (async) · Prisma 7 (schema + migrations only) · uv |
| `apps/web` | Next.js 16 (App Router) · react-hook-form + Zod · Tailwind · openapi-fetch · pnpm |
| Backing services | Postgres 16 · MinIO (S3) · Mailpit (SMTP) — all in docker compose |

## Run it

Requires Docker.

```bash
cp .env.example .env        # local-only values; edit POSTGRES_HOST_PORT if 5432 is taken
docker compose up --build   # or: make up
```

| What | Where |
|---|---|
| Public lead form | http://localhost:3000 |
| Attorney sign-in | http://localhost:3000/login — `attorney@example.com` / `password123` |
| Leads dashboard | http://localhost:3000/leads |
| Email inbox (both emails land here) | http://localhost:8025 |
| API docs (Swagger) | http://localhost:8000/docs |
| MinIO console | http://localhost:9001 (`S3_ACCESS_KEY` / `S3_SECRET_KEY` from `.env`) |

Startup order is enforced by compose: `postgres` → `migrate` (one-shot `prisma migrate deploy`) → `api`
(seeds attorney accounts, then serves) → `web`.

## Develop

Host tooling: [uv](https://docs.astral.sh/uv/), Node ≥ 20.19 with pnpm (web) and npm (Prisma CLI in `apps/api`).

```bash
make services                          # postgres, minio, mailpit only
cd apps/api && uv run uvicorn app.main:app --reload     # :8000 (reads ../../.env)
cd apps/web && pnpm install && pnpm dev                 # :3000, proxies /api → :8000
```

For the host-run API, apply migrations and seed first: `docker compose run --rm migrate && make seed`.

| Command | Does |
|---|---|
| `make test` | API tests (pytest, real Postgres + MinIO) and web tests (Vitest) |
| `make lint` | ruff, ruff format, mypy (strict), tsc |
| `make generate-client` | Dump FastAPI's OpenAPI → `apps/web/openapi.json` → typed client (`schema.d.ts`) |
| `make migrate-dev name=<change>` | Edit `prisma/schema.prisma` first; writes + applies a migration |
| `make db-check` | Drift checks: migrations ↔ `schema.prisma` ↔ live DB ↔ SQLAlchemy models |

### Changing the schema

1. Edit `apps/api/prisma/schema.prisma`.
2. `make migrate-dev name=<change>` and review the generated `migration.sql`.
3. Mirror the change in `apps/api/app/db/models.py` (mapping rules in the design doc §5).
4. `make test` — `tests/test_schema_drift.py` fails if step 3 is missing or wrong.

### Changing the API

After changing routes or schemas, run `make generate-client`; `tests/test_openapi_contract.py` fails
until the web client is regenerated.

## Layout

```
apps/api/
  app/{core,db,schemas,auth,leads,emails,storage}   FastAPI app
  prisma/schema.prisma, prisma/migrations/          source of truth for the data model
  tests/                                            pytest
apps/web/
  src/app/(public)/page.tsx                         lead form  (/)
  src/app/(internal)/leads/…                        dashboard  (/leads, /leads/[id])
  src/app/login/                                    sign in
  src/lib/api/{browser,server}.ts                   the two API clients (same-origin /api vs. cookie-forwarding)
  src/proxy.ts                                      redirect to /login when there's no session cookie
  server-entry.cjs                                  prod entry: stamps X-Forwarded-For (see NOTES.md)
docker/postgres/init.sql                            creates shadow/test/ci databases
scripts/                                            db-check.sh, generate-client.sh, seed.sh
```

## Production switches

Everything is env-driven (see `.env.example`):

- `EMAIL_PROVIDER=resend` + `RESEND_API_KEY` — real email instead of Mailpit.
- `S3_ENDPOINT` unset (or real S3 endpoint), `S3_PUBLIC_ENDPOINT` unset — real S3; credentials via env or IAM role.
- `COOKIE_SECURE=true`, `SESSION_COOKIE_NAME=__Host-session`, `ALLOWED_ORIGINS=https://<web origin>`,
  a real `JWT_SECRET`, and no `SEED_PASSWORD`.
