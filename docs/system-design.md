# Lead Management System — System Design Document

A public lead-intake form for legal prospects with resume upload, dual email notifications, and an authenticated internal dashboard for attorneys to review and manage leads.

---

## Table of Contents

1. [Goals & Non-Goals](#1-goals--non-goals)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Monorepo Layout](#3-monorepo-layout)
4. [Data Model (Prisma)](#4-data-model-prisma)
5. [Why Prisma with a Python API — and How](#5-why-prisma-with-a-python-api--and-how)
6. [API Design (FastAPI)](#6-api-design-fastapi)
7. [Lead State Machine](#7-lead-state-machine)
8. [Authentication & Authorization](#8-authentication--authorization)
9. [File Storage (Resume Uploads)](#9-file-storage-resume-uploads)
10. [Email Subsystem](#10-email-subsystem)
11. [Background Processing & Reliability](#11-background-processing--reliability)
12. [Frontend Design (NextJS)](#12-frontend-design-nextjs)
13. [Security Considerations](#13-security-considerations)
14. [Local Development Environment](#14-local-development-environment)
15. [Testing Strategy](#15-testing-strategy)
16. [Key Trade-offs & Upgrade Paths](#16-key-trade-offs--upgrade-paths)

---

## 1. Goals & Non-Goals

### Functional goals

- **Public lead creation** — prospects submit first name, last name, email, and a resume/CV file with no authentication.
- **Dual email dispatch** — on submission, send a confirmation to the prospect and a notification to an attorney (set).
- **Internal UI** — authenticated attorneys browse leads with all submitted info, download resumes, and transition lead state.
- **Lead lifecycle** — `PENDING → REACHED_OUT`, transition performed manually by an attorney.

### Non-goals (explicitly out of scope)

- Attorney assignment/rotation logic (all `ATTORNEY_EMAILS` receive the notification).
- Reverting `REACHED_OUT` back to `PENDING` or any richer CRM lifecycle (`HIRED`, `REJECTED`, etc.).
- Admin UI for managing attorney accounts (seeded via migration/env for local dev).
- Email template editing UI.
- Multi-tenancy or i18n.

Stating non-goals up front keeps the state machine, permissions model, and data model honest and minimal.

---

## 2. High-Level Architecture

Three services + three backing stores, all orchestrated by docker-compose for local development:

```
                        ┌─────────────────────────────────────────────┐
                        │                 Browser                     │
                        └──────┬─────────────────────────┬────────────┘
                               │                         │
                    public lead form              internal dashboard
                    (NextJS, no auth)             (NextJS, auth cookie)
                               │                         │
                        ┌──────▼─────────────────────────▼──────┐
                        │              NextJS (web)               │
                        │  RSC pages + client form + API client   │
                        └──────────────────┬──────────────────────┘
                                           │  browser calls: same-origin /api/* rewrite
                                           │  RSC calls: direct fetch, session cookie forwarded
                        ┌──────────────────▼──────────────────────┐
                        │            FastAPI (api)                 │
                        │  /leads (public)   /auth   /leads (int.) │
                        │  validation · rate limit · state machine│
                        └──┬──────────────┬──────────────┬────────┘
                           │              │              │
                    ┌──────▼─────┐  ┌─────▼──────┐  ┌────▼─────────┐
                    │  Postgres  │  │    MinIO   │  │ EmailSender  │
                    │(SQLAlchemy)│  │  (resumes) │  │ SMTP/Mailpit │
                    └────────────┘  └────────────┘  │ or Resend    │
                                                    └──────────────┘
```

Submission flow:

```mermaid
sequenceDiagram
    actor P as Prospect
    participant W as NextJS form
    participant A as FastAPI
    participant DB as Postgres
    participant S3 as MinIO
    participant E as EmailSender
    actor T as Attorney

    P->>W: fills form + attaches resume
    W->>W: client-side validation (Zod)
    W->>A: POST /api/v1/leads (multipart)
    A->>A: validate + rate-limit + AV-scan
    A->>S3: upload resume (leads/{id}/resume-{uuid})
    A->>DB: create Lead (PENDING)
    A-->>W: 201 {lead_id}
    A->>A: schedule background task (after response)
    A->>E: send prospect confirmation
    A->>E: send attorney notification
    A->>DB: record EmailLog rows (status/retries)
    T->>A: PATCH /api/v1/leads/{id} (after outreach)
    A->>DB: state PENDING → REACHED_OUT
```

---

## 3. Monorepo Layout

A single public repo (a submission requirement) organized as a lightweight monorepo — no Nx/Turborepo overhead needed at this size:

```
alma-leads/
├── apps/
│   ├── api/                        # FastAPI service
│   │   ├── app/
│   │   │   ├── main.py             # app factory, middleware, router mounting
│   │   │   ├── core/               # settings (pydantic-settings), security, rate limiting
│   │   │   ├── db/                 # SQLAlchemy async engine/session + models (mirror schema.prisma)
│   │   │   ├── schemas/            # pydantic request/response models
│   │   │   ├── auth/               # login, logout, current-user dependency
│   │   │   ├── leads/              # router, service, state machine, tests
│   │   │   ├── emails/             # EmailSender protocol, SMTP + Resend adapters, templates
│   │   │   └── storage/            # S3 client wrapper (upload, presigned GET)
│   │   ├── prisma/
│   │   │   ├── schema.prisma        # single source of truth for the data model
│   │   │   └── migrations/         # prisma migrate artifacts (checked in)
│   │   ├── tests/                  # pytest (httpx AsyncClient, fake EmailSender, schema drift)
│   │   ├── prisma.config.ts        # Prisma 7 config: schema/migrations paths, DB + shadow DB URLs
│   │   ├── package.json            # tooling only: pinned `prisma` 7.x + `dotenv` (no runtime JS)
│   │   ├── package-lock.json
│   │   ├── Dockerfile              # multi-stage: uv builds .venv, runtime stage has no uv
│   │   ├── .python-version         # 3.12 — uv installs it if missing
│   │   ├── pyproject.toml          # deps + dev dependency group (uv-managed)
│   │   └── uv.lock                 # exact resolved versions (checked in)
│   └── web/                        # NextJS (App Router) service
│       ├── src/
│       │   ├── app/
│       │   │   ├── (public)/        # `/` lead form (react-hook-form + Zod)
│       │   │   ├── (internal)/      # `/leads`, `/leads/[id]` (auth-guarded)
│       │   │   └── login/
│       │   ├── components/
│       │   ├── lib/api/             # generated types + browser client (/api) + server client (cookie-forwarding)
│       │   └── middleware.ts        # cookie check → redirect to /login
│       ├── next.config.ts           # /api/* rewrite → FastAPI (same-origin proxy)
│       ├── Dockerfile
│       └── package.json
├── docs/                            # this file, coding-agents.md
├── scripts/                        # seed attorney account, generate client, db-check.sh
├── docker-compose.yml               # postgres, minio, mailpit, api, web
├── Makefile                         # common commands
├── NOTES.md                         # agent vs. hand-written attribution
└── README.md                        # local run instructions
```

### Python toolchain: uv

The API is a **uv project**: `pyproject.toml` declares dependencies, `uv.lock` pins every resolved version (checked in), and uv creates and owns `apps/api/.venv`. There is no `requirements.txt`, no `pip install`, and no manual virtualenv step. One tool replaces pip, venv, pip-tools, and pyenv, and every environment (laptop, CI, Docker) installs from the same lockfile.

```toml
# apps/api/pyproject.toml
[project]
name = "alma-leads-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "pydantic-settings",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg",
    "pwdlib[argon2]",
    "pyjwt",
    "python-multipart",   # FastAPI multipart parsing (resume upload)
    "python-magic",       # content sniffing; needs libmagic1 in the image
    "boto3",
    "slowapi",
    "jinja2",
    "aiosmtplib",
    "resend",
]

[dependency-groups]
dev = [
    "pytest",
    "pytest-asyncio",
    "httpx",
    "alembic",            # test-only: compare_metadata in the drift test, never runs migrations
    "ruff",
    "mypy",
]

[tool.pytest.ini_options]
pythonpath = ["."]
asyncio_mode = "auto"
```

- **No `[build-system]`**, so uv treats the API as an application, not a package: it installs the dependencies into `.venv` but doesn't build or install `app/` itself. `app` is imported from the working directory (`uvicorn app.main:app`, `pythonpath = ["."]` for pytest).
- **Alembic is a dev dependency only.** It exists for the drift test ([§5](#drift-protection)) and never reaches the runtime image.
- **`--locked` everywhere outside a developer's laptop** (CI, Docker): `uv sync --locked` fails if `uv.lock` is out of date with `pyproject.toml`, instead of silently re-resolving. A PR that changes dependencies must commit the updated lockfile.

| Task | Command (from `apps/api/`) |
|---|---|
| Create/update `.venv` from the lockfile (dev group included) | `uv sync` |
| Add a runtime / dev dependency | `uv add <pkg>` / `uv add --dev <pkg>` (updates `pyproject.toml` + `uv.lock`) |
| Upgrade one dependency | `uv lock --upgrade-package <pkg>` then `uv sync` |
| Run the API with reload | `uv run uvicorn app.main:app --reload` |
| Tests / lint / types | `uv run pytest` · `uv run ruff check .` · `uv run mypy app` |

`uv run` syncs `.venv` before executing, so nobody activates a virtualenv by hand. The `Makefile` targets (`make test`, `make lint`, …) are thin wrappers over these commands.

---

## 4. Data Model (Prisma)

Three tables, defined in `schema.prisma` and mirrored as SQLAlchemy models ([§5](#5-why-prisma-with-a-python-api--and-how)). `EmailLog` exists because "did the emails send?" is the first debugging question when someone says "the attorney never got a notification" — the audit rows answer it without guessing.

```prisma
model Lead {
  id           String     @id @default(uuid())
  firstName    String
  lastName     String
  email        String
  state        LeadState  @default(PENDING)
  resumeKey    String      // S3 object key, never a public URL
  resumeName   String      // original filename for display
  resumeSize   Int
  resumeMime   String
  createdAt    DateTime   @default(now())
  updatedAt    DateTime   @updatedAt
  reachedOutAt DateTime?
  reachedOutBy String?     // User.id who transitioned the lead
  reachedOutUser User?   @relation("ReachedOutBy", fields: [reachedOutBy], references: [id])
  emails       EmailLog[]

  @@index([state, createdAt])
  @@index([createdAt])
}

model User {
  id           String   @id @default(uuid())
  email        String   @unique
  passwordHash String
  name         String
  role         UserRole @default(ATTORNEY)
  createdAt    DateTime @default(now())
  leadsReached Lead[]   @relation("ReachedOutBy")
}

model EmailLog {
  id          String     @id @default(uuid())
  leadId      String
  lead        Lead       @relation(fields: [leadId], references: [id], onDelete: Cascade)
  kind        EmailKind  // PROSPECT_CONFIRMATION | ATTORNEY_NOTIFICATION
  recipient   String
  status      EmailStatus @default(PENDING) // PENDING|SENT|FAILED
  providerId  String?     // Resend message id, etc.
  error       String?
  attempts    Int         @default(0)
  sentAt      DateTime?
  createdAt   DateTime    @default(now())

  @@index([leadId])
  @@index([status])
}

enum LeadState {
  PENDING
  REACHED_OUT
}

enum UserRole {
  ATTORNEY
  ADMIN
}

enum EmailKind {
  PROSPECT_CONFIRMATION
  ATTORNEY_NOTIFICATION
}

enum EmailStatus {
  PENDING
  SENT
  FAILED
}
```

Design notes:

- **UUIDs, not auto-increment** — the public submission response returns an ID; sequential ints leak submission volume.
- **`resumeKey`, not `resumeUrl`** — URLs expire (presigned); keys are stable. Download URLs are minted per-request for authorized users only.
- **`reachedOutBy` / `reachedOutAt`** — free audit trail for the state transition; trivially useful in an attorney-facing tool.
- **No `Lead.attorneyId`** — no assignment requirement, so no assignment column. Adding one later is a nullable FK away.
- **`@@index([state, createdAt])`** — the dashboard's default view is "pending leads, newest first", which is exactly this index.

---

## 5. Why Prisma with a Python API — and How

This is the most opinionated constraint in the stack: **Prisma is a JS/TS ecosystem and our API is FastAPI.**

The historical bridge, `prisma-client-py`, is **deprecated and no longer maintained**. It pins old Prisma engine binaries, won't track new Prisma releases, and would leave the whole data layer of a legal-data app on an abandoned dependency. So the design splits Prisma's two jobs apart:

**Prisma owns the schema and migrations. SQLAlchemy 2.0 (async, `asyncpg`) owns every runtime query.**

| Concern | Owner | Artifact |
|---|---|---|
| Data model definition | Prisma | `prisma/schema.prisma` (single source of truth) |
| Migration SQL + history | Prisma CLI (`prisma migrate dev`) | `prisma/migrations/*/migration.sql` (checked in, reviewed) |
| Applying migrations | Prisma CLI (`prisma migrate deploy`) | one-shot `migrate` container ([§14](#14-local-development-environment)) |
| Runtime reads/writes | SQLAlchemy 2.0 async | `app/db/models.py`, `app/db/session.py` |
| Keeping the two in sync | CI drift checks | `scripts/db-check.sh` (`prisma migrate diff` + `tests/test_schema_drift.py`) |

`schema.prisma` has a `datasource` block but **no `generator` block** — `prisma generate` never runs and there is no Prisma client anywhere. Prisma is a DDL-authoring tool; Node exists only in the dev toolchain and the `migrate` image, never in the API runtime.

### Prisma version and configuration

**Pinned to Prisma ORM 7.** Prisma 7 changed exactly the parts this design depends on: connection URLs moved out of `schema.prisma` into `prisma.config.ts`, `.env` is no longer loaded automatically, and `prisma migrate diff` dropped `--from-url`/`--to-url`/`--shadow-database-url` in favor of `--from-config-datasource`/`--to-config-datasource` plus a shadow URL in the config file. Commands written for Prisma 6 fail on 7 and the reverse, so the major version is fixed:

```jsonc
// apps/api/package.json — tooling only; nothing here ships in the API image
{
  "private": true,
  "engines": { "node": ">=20.19.0" },       // Prisma 7 minimum
  "devDependencies": {
    "prisma": "^7.0.0",                      // major pinned; exact version locked by package-lock.json
    "dotenv": "^17.0.0"
  }
}
```

`npm ci` everywhere (dev, CI, `migrate` image) installs the exact locked version. Moving to Prisma 8 is a deliberate change: bump the range, re-read the `migrate diff` and config reference, and re-run `make db-check`.

```prisma
// apps/api/prisma/schema.prisma — no url here in Prisma 7, and no generator block
datasource db {
  provider = "postgresql"
}
```

```ts
// apps/api/prisma.config.ts — run Prisma CLI from apps/api so npx finds this file
import "dotenv/config"; // Prisma 7 does not load .env on its own
import { defineConfig, env } from "prisma/config";

export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: { path: "prisma/migrations" },
  datasource: {
    url: env("DATABASE_URL"), // env() throws if unset — fail fast, never migrate "nowhere"
    // Only for `migrate diff --from-migrations` (and `migrate dev`). Read via process.env
    // because it's optional: unset in production, where only `migrate deploy` runs.
    shadowDatabaseUrl: process.env.SHADOW_DATABASE_URL,
  },
});
```

`DATABASE_URL` is the one URL both tools read: Prisma uses it as-is (`postgresql://…`) and the API's `Settings.sqlalchemy_url` rewrites the scheme to `postgresql+asyncpg://…`.

### Options considered

| Option | Verdict |
|---|---|
| `prisma-client-py` | **Rejected.** Deprecated/unmaintained; engine binaries frozen at an old Prisma version; no security fixes. |
| Node sidecar running Prisma Client JS, called from FastAPI over HTTP | **Rejected.** A fourth service, a network hop per query, and transactions that can't span the Python boundary — for three tables. |
| Prisma migrations + raw `asyncpg` SQL | Viable, but hand-mapping rows to objects and hand-building filter/pagination SQL reinvents the parts of an ORM we'd actually use. |
| Drop Prisma: SQLAlchemy + Alembic | Cleanest pure-Python story, but drops the Prisma requirement. Recorded as the upgrade path ([§16](#16-key-trade-offs--upgrade-paths)). |
| **Prisma CLI for schema/migrations + SQLAlchemy for queries** | **Chosen.** Each tool does the one job it's maintained for. |

The honest cost of the chosen option is that **the model is described twice** — once in `schema.prisma`, once as SQLAlchemy mappings — and duplication is exactly where schema drift bugs are born. This isn't "two ORMs, two mental models": application code only ever sees SQLAlchemy; Prisma is touched only when changing the schema. The duplication is real, though, so it's made **mechanically checked** rather than trusted (see *Drift protection* below).

### Mapping rules: map to the tables, not to the Prisma schema

SQLAlchemy models describe **the tables Prisma's migrations create**. That distinction matters because several Prisma attributes are implemented by the Prisma *client*, not the database — with no client, the API must supply those behaviors itself:

| Prisma | What actually lands in Postgres | SQLAlchemy mapping |
|---|---|---|
| `id String @id @default(uuid())` | `TEXT PRIMARY KEY`, **no DB default** (client-generated) | `mapped_column(primary_key=True, default=lambda: str(uuid4()))` |
| `@updatedAt` | plain `TIMESTAMP(3) NOT NULL`, **no trigger** (client-maintained) | `default=func.now(), onupdate=func.now()` |
| `@default(now())` | `DEFAULT CURRENT_TIMESTAMP` | `server_default=func.now()` (DB does it) |
| `String` / `DateTime` | `TEXT` / `TIMESTAMP(3)` | `type_annotation_map = {str: Text, datetime: TIMESTAMP(precision=3)}` on `Base` |
| `enum LeadState` | Postgres enum type `"LeadState"` | `Enum(LeadState, name="LeadState", create_type=False)` — Prisma creates the type, SQLAlchemy never does |
| model `Lead`, field `firstName` | table `"Lead"`, quoted column `"firstName"` | `__tablename__ = "Lead"`; `first_name = mapped_column("firstName")` — Pythonic attribute, exact column |
| `@@index([state, createdAt])` | index `Lead_state_createdAt_idx` | `Index("Lead_state_createdAt_idx", "state", "createdAt")` — same name, or the drift check flags it |
| `email String @unique` | unique index `User_email_key` | `Index("User_email_key", "email", unique=True)` (not `unique=True` on the column, which creates a constraint instead) |

Excerpt:

```python
# app/db/models.py — mirrors prisma/schema.prisma; drift-checked in CI
class Base(DeclarativeBase):
    type_annotation_map = {str: Text, datetime: TIMESTAMP(precision=3)}


class Lead(Base):
    __tablename__ = "Lead"
    __table_args__ = (
        Index("Lead_state_createdAt_idx", "state", "createdAt"),
        Index("Lead_createdAt_idx", "createdAt"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    first_name: Mapped[str] = mapped_column("firstName")
    last_name: Mapped[str] = mapped_column("lastName")
    email: Mapped[str]
    state: Mapped[LeadState] = mapped_column(
        Enum(LeadState, name="LeadState", create_type=False), default=LeadState.PENDING
    )
    resume_key: Mapped[str] = mapped_column("resumeKey")
    # ... resumeName, resumeSize, resumeMime
    created_at: Mapped[datetime] = mapped_column("createdAt", server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column("updatedAt", default=func.now(), onupdate=func.now())
    reached_out_at: Mapped[datetime | None] = mapped_column("reachedOutAt")
    reached_out_by: Mapped[str | None] = mapped_column("reachedOutBy", ForeignKey("User.id"))

    emails: Mapped[list["EmailLog"]] = relationship(back_populates="lead")
```

(Alternative considered: `@map("first_name")` / `@@map("leads")` in `schema.prisma` for a snake_case database. Rejected to keep the Prisma schema idiomatic and in the form reviewers expect; explicit column names in `mapped_column` cost one string per field.)

### Sessions and transactions

```python
# app/db/session.py
engine = create_async_engine(
    settings.sqlalchemy_url,  # postgresql+asyncpg://…
    pool_pre_ping=True,
    connect_args={"server_settings": {"timezone": "UTC"}},
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
```

- **One `DATABASE_URL` env var.** Prisma needs `postgresql://…`; SQLAlchemy needs `postgresql+asyncpg://…`. `Settings.sqlalchemy_url` derives the second from the first so the two tools can never point at different databases.
- **UTC everywhere.** `TIMESTAMP(3)` has no time zone; pinning the session `timezone` to UTC makes `CURRENT_TIMESTAMP`/`func.now()` agree with Python-side `datetime.now(UTC)`.
- **Request-scoped session via FastAPI dependency; the service layer owns transaction boundaries** (`async with session.begin():`). Handlers never commit.
- **`expire_on_commit=False`** so response models can be built from ORM objects after commit without async lazy-load errors; relationships are loaded explicitly (`selectinload`) — lazy loading is off-limits under asyncio.
- The lead-create path writes the `Lead` row **after** the S3 upload succeeds and inside a single transaction; if the insert fails, the orphaned object is deleted best-effort (and is unreachable anyway, since nothing references its key).

The state transition from [§7](#7-lead-state-machine) is a **single conditional `UPDATE`**, which makes the guard race-free — two attorneys clicking at once can't both win:

```python
async def mark_reached_out(session: AsyncSession, lead_id: str, attorney_id: str) -> Lead:
    async with session.begin():
        lead = await session.scalar(
            update(Lead)
            .where(Lead.id == lead_id, Lead.state.in_(sources_for(LeadState.REACHED_OUT)))
            .values(state=LeadState.REACHED_OUT, reached_out_at=func.now(), reached_out_by=attorney_id)
            .returning(Lead)
        )
        if lead is None:
            # zero rows: lead missing (404) or not in an allowed source state (409)
            exists = await session.scalar(select(Lead.id).where(Lead.id == lead_id))
            raise LeadNotFound() if exists is None else InvalidTransition()
    return lead
```

`sources_for()` is derived from `ALLOWED_TRANSITIONS`, so the state machine is still defined in one place.

### Drift protection

Two links in the chain can drift, and CI checks both:

```
schema.prisma ──(1) prisma migrate diff──► migrations/*.sql ──migrate deploy──► Postgres ◄──(2) compare_metadata── app/db/models.py
```

1. **Schema ↔ migrations:** `prisma migrate diff --from-migrations prisma/migrations --to-schema prisma/schema.prisma --exit-code`. Prisma replays every migration into the **shadow database** (`datasource.shadowDatabaseUrl`), introspects the result, and diffs it against `schema.prisma`. With `--exit-code` the result is `0` = in sync, `1` = error, `2` = drift — someone edited the schema without generating a migration.
2. **Database ↔ SQLAlchemy models:** after `prisma migrate deploy` applies the migrations to a throwaway Postgres, a pytest test uses Alembic's `compare_metadata` **as a library only** (Alembic never runs a migration) to diff the live schema against `Base.metadata`:

```python
# tests/test_schema_drift.py
def _diff(sync_conn):
    ctx = MigrationContext.configure(
        sync_conn,
        opts={
            "compare_type": True,
            "include_name": lambda name, type_, _: not (type_ == "table" and name == "_prisma_migrations"),
        },
    )
    return compare_metadata(ctx, Base.metadata)


async def test_models_match_prisma_migrations(migrated_engine):
    async with migrated_engine.connect() as conn:
        assert await conn.run_sync(_diff) == []
```

   `compare_metadata` catches missing/extra tables, columns, types, nullability, indexes, and foreign keys. It doesn't compare enum *values*, so a second small test checks each Python enum's members against `pg_enum` for the matching type.

Both checks live in one script so local runs (`make db-check`) and CI are the same command:

```bash
#!/usr/bin/env bash
# scripts/db-check.sh — needs two EMPTY, throwaway databases.
# The shadow DB is wiped on every run: never point SHADOW_DATABASE_URL at real data.
set -euo pipefail
cd "$(dirname "$0")/../apps/api"   # npx only finds prisma.config.ts from this directory

: "${DATABASE_URL:?must be set}"
: "${SHADOW_DATABASE_URL:?must be set}"

npx prisma validate

# (1) migration history ↔ schema.prisma (replayed in the shadow DB). Exit 2 = drift.
npx prisma migrate diff \
  --from-migrations prisma/migrations \
  --to-schema prisma/schema.prisma \
  --exit-code

# Apply migrations to the CI database, then confirm the live DB matches schema.prisma.
# This second diff only introspects, so the same command also detects hand-edits on staging.
npx prisma migrate deploy
npx prisma migrate diff \
  --from-config-datasource \
  --to-schema prisma/schema.prisma \
  --exit-code

# (2) live DB ↔ SQLAlchemy models (compare_metadata + pg_enum checks)
uv run --locked pytest tests/test_schema_drift.py
```

CI job (GitHub Actions), version-matched to the pins above:

```yaml
db-check:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:16
      env: { POSTGRES_PASSWORD: postgres }
      ports: ["5432:5432"]
      options: >-
        --health-cmd pg_isready --health-interval 5s --health-timeout 5s --health-retries 10
  env:
    DATABASE_URL: postgresql://postgres:postgres@localhost:5432/alma_ci
    SHADOW_DATABASE_URL: postgresql://postgres:postgres@localhost:5432/alma_ci_shadow
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: 22
        cache: npm
        cache-dependency-path: apps/api/package-lock.json
    - uses: astral-sh/setup-uv@v9
      with:
        version: "0.12.19"                         # pin uv itself, like Prisma
        enable-cache: true
        cache-dependency-glob: apps/api/uv.lock
    - run: npm ci
      working-directory: apps/api
    - run: uv sync --locked                        # installs Python 3.12 from .python-version if needed
      working-directory: apps/api
    - run: >-
        psql postgresql://postgres:postgres@localhost:5432/postgres
        -c 'CREATE DATABASE alma_ci' -c 'CREATE DATABASE alma_ci_shadow'
    - run: scripts/db-check.sh
```

### Schema-change workflow

1. Edit `prisma/schema.prisma`.
2. `make migrate-dev name=<change>` → `prisma migrate dev --name <change>`: writes the SQL migration and applies it to the local DB.
3. Review the generated `migration.sql` (it's what production runs — treat it as code).
4. Update `app/db/models.py` using the mapping rules above.
5. `make test` — the drift test fails if step 4 was skipped or wrong; `make db-check` runs `scripts/db-check.sh` against the local `alma` + `alma_shadow` databases.

---

## 6. API Design (FastAPI)

Versioned under `/api/v1`. Two routers: public (`leads_public`, `auth`) and internal (`leads`), with a dependency chain that enforces the boundary.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/leads` | none (rate-limited) | Public lead submission (multipart) |
| `POST` | `/api/v1/auth/login` | none | Login → sets `httpOnly` cookie |
| `POST` | `/api/v1/auth/logout` | none | Clears cookie |
| `GET` | `/api/v1/auth/me` | attorney | Current session user |
| `GET` | `/api/v1/leads` | attorney | List leads — pagination, `state` filter, sort |
| `GET` | `/api/v1/leads/{id}` | attorney | Lead detail + resume metadata |
| `GET` | `/api/v1/leads/{id}/resume` | attorney | Presigned download URL for the resume |
| `PATCH` | `/api/v1/leads/{id}` | attorney | State transition (`PENDING → REACHED_OUT`) |

Key decisions:

- **`multipart/form-data` on public create** — required for the file; Pydantic validation for the text fields (non-empty, max lengths, email format) and manual validation for the file (size + MIME sniffing, see [§9](#9-file-storage-resume-uploads)).
- **Create returns only `{id}` + a generic message** — no reason to echo more data to an anonymous submitter.
- **Resume download is a separate, authorized endpoint** that returns a **presigned URL** — the object store handles the bytes; the API handles the authorization. A public resume endpoint would be the worst kind of leak in a legal context.
- **Pagination from day one** (`?page=&pageSize=&state=`) — the internal list is the app's main screen; it should not degrade after a few hundred leads. Cursor-based pagination noted as an upgrade path but offset is fine at this scale.
- **OpenAPI as the contract** — FastAPI emits the schema; the NextJS API client is generated from it (see [§12](#12-frontend-design-nextjs)). The contract can't drift if only one side hand-writes it.

---

## 7. Lead State Machine

```
                 manual action by attorney
         ┌──────────────────────────────────────┐
         │                                      │
   [created] ──► PENDING ──────────────────────► REACHED_OUT
                     │
                     └─ (no other outgoing edges)
```

- The transition is the **only** mutation on a lead after creation, so it's a dedicated service-layer function with an explicit guard:

```python
ALLOWED_TRANSITIONS = {
    LeadState.PENDING: {LeadState.REACHED_OUT},
}

# PATCH /leads/{id} with {"state": "REACHED_OUT"}
# → 409 CONFLICT if current state has no edge to the target
```

- **409 on invalid transition, not a silent no-op** — an explicit error surfaces UI bugs and prevents the "double-click marked it twice" ambiguity from being swallowed.
- The guard lives in one place (service layer), not in the handler or the client — the API is the enforcement point regardless of what the UI does.
- `reachedOutAt`/`reachedOutBy` are stamped by the same function that flips the state, atomically.

---

## 8. Authentication & Authorization

**Email + password with a JWT in an `httpOnly` cookie.** No external identity provider — a take-home must run locally with zero third-party setup, and this keeps the auth flow fully demonstrable end-to-end.

- **Hashing:** Argon2id (via `pwdlib`) — the current OWASP-recommended choice; plaintext or fast hashes are non-negotiable non-options.
- **Token:** short-lived (8h) signed JWT (HS256, secret from env) in an `httpOnly` cookie (full attributes below). `httpOnly` keeps the token out of reach of XSS; the internal UI is a browser app on one origin, not a mobile client, so a cookie beats a `Bearer` header here.
- **Enforcement:** a FastAPI dependency (`get_current_attorney`) on every internal route. NextJS `middleware.ts` additionally redirects unauthenticated page requests to `/login` — UX sugar, not a security boundary (the API is).
- **Local dev seeding:** a startup script creates `attorney@example.com` / `password123` (and any `ATTORNEY_EMAILS` rows needed) so the demo works out of the box.
- **Login rate limiting** on `/auth/login` to blunt credential stuffing.

### Browser → API path: one origin via an `/api` proxy

`web` (`:3000`) and `api` (`:8000`) are **different origins**, so letting the browser call FastAPI directly would need credentialed CORS, and the cookie would belong to a different origin than the pages. Instead, **the browser only ever talks to the NextJS origin.** NextJS rewrites `/api/*` to FastAPI on the container network:

```ts
// apps/web/next.config.ts
const nextConfig: NextConfig = {
  async rewrites() {
    // API_INTERNAL_URL=http://api:8000 — resolved at `next build`, so it's passed as a build arg
    return [{ source: "/api/:path*", destination: `${process.env.API_INTERNAL_URL}/api/:path*` }];
  },
};
```

| Option | Verdict |
|---|---|
| **Same-origin `/api/*` rewrite in NextJS** | **Chosen.** No CORS at all; the cookie is a host-only cookie on the web origin; the Origin check has exactly one allowed value. |
| Browser calls `:8000` directly with `credentials: "include"` | Rejected. Needs `CORSMiddleware(allow_origins=[…], allow_credentials=True)`, a preflight on every `PATCH`, and a cookie that must be sent to an origin other than the page's. More configuration, more ways to get it wrong. |
| NextJS Route Handlers re-implementing each endpoint as a BFF | Rejected. A hand-written second API surface that must track FastAPI's; the rewrite passes bytes through untouched, multipart uploads included. |

There are **two call paths**, and each is set up once in `src/lib/api/`:

| Caller | Route | How the cookie travels |
|---|---|---|
| Client components (form submit, login, logout, "Mark as reached out") | browser → `http://localhost:3000/api/v1/…` → rewrite → `http://api:8000/api/v1/…` | Browser sends it automatically (`credentials: "same-origin"`, the fetch default, set explicitly). `Set-Cookie` from `/auth/login` passes back through the rewrite, so the browser stores it for the web origin. |
| Server components (list + detail pages) | NextJS server → `API_INTERNAL_URL` directly (skips the rewrite hop) | Server code has no browser cookie jar, so it **forwards the session cookie from the incoming request** explicitly. |

```ts
// src/lib/api/browser.ts — client components
export const browserApi = createClient<paths>({ baseUrl: "", credentials: "same-origin" });

// src/lib/api/server.ts — server components only
import "server-only";
import { cookies } from "next/headers";

export async function serverApi() {
  const session = (await cookies()).get(SESSION_COOKIE);
  return createClient<paths>({
    baseUrl: process.env.API_INTERNAL_URL,              // container network; never sent to the browser
    headers: session ? { cookie: `${SESSION_COOKIE}=${session.value}` } : {}, // forward only the session cookie
    cache: "no-store",                                   // per-user data: never cache across requests
  });
}
```

Rules that keep this simple:

- **Server components only read (`GET`).** Every write goes browser → `/api` → FastAPI, so every write carries the browser's `Origin` and passes the check below. No Server Actions or Route Handlers issue writes — they would reach FastAPI from the NextJS server without the browser's `Origin`, and need their own CSRF story.
- **A 401 in a server component** → `redirect("/login?next=…")`. **A 401 in the browser client** → same redirect from a shared response handler.
- **`middleware.ts` matches only page routes** (`matcher: ["/leads/:path*"]`), never `/api/*`, so proxied requests (including resume uploads) pass through untouched.
- **Client IPs survive the proxy.** Without extra setup, every request would reach FastAPI from the `web` container's IP, and per-IP rate limiting would treat all users as one. `uvicorn` runs with `--proxy-headers` and `FORWARDED_ALLOW_IPS=<web service address>`, so `request.client.host` comes from `X-Forwarded-For` only when the hop is the trusted proxy. An integration test sends two different forwarded IPs and asserts they get separate rate-limit buckets.
- **FastAPI mounts no `CORSMiddleware`.** It never sends `Access-Control-Allow-Origin`, so no other origin can read its responses.
- **Production has the same shape:** either keep the NextJS rewrite, or route `/api/*` to the API at the load balancer. Both keep one origin.

### Session cookie

| Attribute | Value | Why |
|---|---|---|
| Name | `__Host-session` in prod; `session` in local dev | The `__Host-` prefix makes the browser refuse the cookie unless it's `Secure`, `Path=/`, and has no `Domain`, so a sibling subdomain can't plant or overwrite it. It needs HTTPS, so dev over plain `http://localhost` uses the bare name (`SESSION_COOKIE_NAME` env). |
| `HttpOnly` | always | JS (and therefore XSS) can't read the token. |
| `Secure` | prod; off in local http dev (`COOKIE_SECURE` env) | Never sent over plaintext in production. |
| `SameSite` | `Lax` | `Strict` would drop the cookie when an attorney clicks the deep link in the notification email (a cross-site top-level navigation) and bounce them to `/login`. `Lax` sends it cross-site only on top-level `GET` navigations, and every `GET` here is side-effect-free. |
| `Domain` | unset (host-only) | Sent only to the exact host that set it. |
| `Path` | `/` | Required by `__Host-`; covers pages and `/api`. |
| `Max-Age` | `28800` (8h) | Matches the JWT `exp`, so the cookie and the token expire together. |

`/auth/logout` clears it with the same name/path/attributes (a mismatch leaves the old cookie in place).

### CSRF: Origin check on every unsafe request

`SameSite=Lax` is **not** a same-origin guarantee. "Same-site" ignores ports and subdomains: `http://localhost:8025` (Mailpit) and `:9001` (MinIO console) are same-site with `:3000`, and in production any `*.example.com` page is same-site with `app.example.com`. A request from any of them carries a `Lax` cookie. And CORS doesn't stop a cross-origin request from being *sent* — a `multipart/form-data` or empty-body `POST` (e.g. logout) needs no preflight. So FastAPI verifies the origin itself:

```python
# app/core/security.py — applied to every POST/PUT/PATCH/DELETE, including /auth/login and /auth/logout
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

async def enforce_same_origin(request: Request, call_next):
    if request.method in UNSAFE_METHODS:
        fetch_site = request.headers.get("sec-fetch-site")
        origin = request.headers.get("origin")
        if (fetch_site is not None and fetch_site != "same-origin") or origin not in settings.allowed_origins:
            return JSONResponse({"detail": "Cross-origin request rejected"}, status_code=403)
    return await call_next(request)
```

- **`ALLOWED_ORIGINS`** is an exact-match list: `http://localhost:3000` locally, the production web origin in prod. No wildcards, no suffix matching.
- **`Origin` is required, not just checked when present.** Browsers send `Origin` on every non-`GET`/`HEAD` fetch, same-origin included, so a missing header means "not our browser client" → 403. `Sec-Fetch-Site`, when the browser sends it, must be `same-origin`. Through the rewrite, the page and the request URL are both `:3000`, so legitimate calls always pass.
- **Login and logout are covered too:** login CSRF (logging a victim into an attacker's account) and forced logout are both real attacks.
- **The public `POST /leads` is covered as well.** It has no cookie to protect, but one rule with no per-route exceptions is easier to get right, and the only legitimate caller is our own form.
- **Depth:** `PATCH` and `/auth/login` accept only `application/json`, which forces a CORS preflight for any cross-origin caller, and the preflight fails because no CORS headers are sent.
- **Why not a CSRF token:** a synchronizer or double-submit token needs a JS-readable token plus header plumbing in both API clients, and protects nothing extra when every write comes from a modern browser via `fetch`. A token is the upgrade if a non-browser or legacy client ever needs cookie auth.
- **Swagger UI** (`:8000/docs`) is its own origin, so its "Try it out" writes are rejected unless `http://localhost:8000` is in `ALLOWED_ORIGINS`. `.env.example` includes it for local dev only.

---

## 9. File Storage (Resume Uploads)

**S3-compatible object storage; MinIO locally, S3 in production.** Same API surface, so "prod-ify" is an env-var change (`S3_ENDPOINT` pointed at real S3), not a code change.

- **Client-side:** accept `pdf, doc, docx`; enforce a max size (5 MB default, env-tunable) both in the browser (fail fast) and in the API (enforce).
- **Server-side validation, in order:**
  1. Size check (reject before buffering the whole file).
  2. Extension allowlist **plus content sniffing** (`python-magic`/mimetypes against the first bytes) — a renamed `.exe` should fail.
  3. (Documented upgrade path: ClamAV container for AV scanning; out of scope locally, noted as a production hardening step.)
- **Object keys:** `leads/{lead_id}/resume-{uuid}{ext}` — UUIDs prevent filename collisions and path traversal tricks; the original filename is preserved as `resumeName` for display.
- **Never public.** The bucket has no public-read policy. Downloads for attorneys go through `GET /leads/{id}/resume`, which checks auth and returns a **short-lived presigned URL** (5 min).
- Storing resumes in Postgres (`bytea`) was rejected: it bloats the DB and its backups, couples page-cache pressure to file size, and still leaves you needing real object storage in production. Local-disk storage was rejected: it breaks with more than one API instance and isn't how anything runs in production anyway.

---

## 10. Email Subsystem

**A provider-agnostic `EmailSender` protocol with two adapters, selected by env var:**

```python
class EmailSender(Protocol):
    async def send(
        self, to: str, subject: str, html: str, text: str, reply_to: str | None = None
    ) -> str:  # returns provider message id
        ...
```

- **`SMTPSender`** — talks to the local **Mailpit** container (`:1025`). Local dev needs **zero credentials** and gets a web inbox at `:8025` where you can literally watch both emails arrive. This is the local default.
- **`ResendSender`** — the production adapter (clean API, generous free tier), enabled by setting `EMAIL_PROVIDER=resend` + `RESEND_API_KEY`.

The protocol is the important part: the lead-intake flow depends on "an email got sent", never on "Resend's payload format". Swapping to SES/SendGrid later is a new adapter plus one env var.

**Two emails per submission:**

| Kind | To | Content |
|---|---|---|
| `PROSPECT_CONFIRMATION` | lead's email | "We received your application" + what happens next |
| `ATTORNEY_NOTIFICATION` | every `ATTORNEY_EMAILS` | New-lead alert with all submitted info + deep link to the internal lead detail |

- **Recipients from env, not a DB table** — there's no assignment requirement, so a table would be schema for schema's sake. A table becomes worthwhile the moment rotation/round-robin is real.
- Templates are plain Jinja2 + inline CSS in `app/emails/templates/` (email HTML circa 2009; no React email toolchain needed).
- Every send — attempt, success, or failure — is recorded in `EmailLog` (see [§11](#11-background-processing--reliability)).

---

## 11. Background Processing & Reliability

**FastAPI `BackgroundTasks` + an `EmailLog` audit table + bounded retries.**

The response to the prospect returns **before** the emails send — SMTP latency (or an outage) shouldn't make the form feel broken, and a prospect shouldn't lose their submission because a third-party mail API hiccuped.

Flow: transaction commits → response returns → background task runs → for each email kind: upsert `EmailLog(PENDING)` → attempt send → on success mark `SENT` with `providerId`; on failure mark `FAILED`, record `error`, increment `attempts`. Retries: up to 3 attempts with exponential backoff (1s/5s/25s) within the task; anything still failing stays as a `FAILED` row — visible, not silent.

**Why not a real queue (Celery/arq) now?** For two emails per submission at take-home scale, a Redis + worker container tripled the moving parts in `docker-compose` and the local-run instructions, for an observability benefit the `EmailLog` table already delivers at this scale. **The upgrade path is explicit and cheap:** the background task's body is a single `send_lead_emails(lead_id)` function behind the same `EmailSender` protocol — moving it to an arq/Celery worker is a transport swap, not a rewrite. The design doc records this as the first change to make when volume justifies it (a second API instance also forces the issue, since in-process background tasks are not shared across workers — at which point the queue arrives on its own schedule).

---

## 12. Frontend Design (NextJS)

**App Router, two route groups split by trust boundary:**

```
src/app/
├── (public)/
│   └── page.tsx          # "/" — lead form
├── (internal)/
│   ├── leads/
│   │   ├── page.tsx      # list: state filter, pagination
│   │   └── [id]/page.tsx # detail: all fields, resume download, transition button
├── login/page.tsx
└── middleware.ts         # cookie present? else redirect to /login
```

- **Public form:** `react-hook-form` + **Zod** schemas that mirror the API's validation (field lengths, email format, file type/size) — client-side validation for UX, with the API as the real enforcement point. Optimistic, accessible error states (field-level messages, not a red banner of doom).
- **Internal list:** server components fetching via the API client; state filter tabs (Pending / Reached Out / All); the "Mark as reached out" action is an optimistic client transition with rollback on 4xx.
- **Auth:** two API clients from one generated schema (see [§8](#browser--api-path-one-origin-via-an-api-proxy)). `browserApi` calls relative `/api/v1/…` URLs through the same-origin rewrite, so the browser attaches the cookie. `serverApi()` calls `API_INTERNAL_URL` directly and forwards the incoming session cookie. Server components only read; all writes go through `browserApi`. On 401 both redirect to `/login?next=…`. `middleware.ts` gives the redirect UX for deep links; the API guards actual data.
- **Generated API client:** `openapi-typescript` + `openapi-fetch` generate a typed client from FastAPI's OpenAPI schema at build time — same philosophy as the data layer: **one side of every contract is the source of truth, and the other is generated or mechanically checked against it.** Route params and response types are compile-checked against the real backend contract, and `make generate-client` regenerates after API changes.
- **Styling:** Tailwind (utility-first, zero component-library lock-in for a small two-screen app).

---

## 13. Security Considerations

| Concern | Mitigation |
|---|---|
| Anonymous public write endpoint | Strict Pydantic validation (lengths, email format), file type/size/MIME enforcement, per-IP rate limiting (`slowapi`, e.g. 5 submissions/15 min/IP) |
| Resume confidentiality (legal data) | Private bucket, no public URLs, presigned GET minted per authorized request, 5-min TTL |
| XSS | No raw HTML rendering of lead fields in the dashboard (React escapes by default); token in `httpOnly` cookie |
| CSRF | Origin check (exact-match `ALLOWED_ORIGINS`, `Origin` required, `Sec-Fetch-Site` must be `same-origin`) on every unsafe method, auth routes included; JSON-only `content-type` on `PATCH`/login; `SameSite=Lax` as depth, not the control ([§8](#csrf-origin-check-on-every-unsafe-request)) |
| Cross-origin reads | No CORS middleware, so no other origin can read responses; browser traffic reaches the API only via the same-origin `/api` rewrite |
| Session cookie theft/planting | `HttpOnly`, `Secure`, host-only, `__Host-` prefix in prod; 8h expiry matched to the JWT |
| Credential stuffing | Rate limit on `/auth/login`; Argon2id hashing |
| Path traversal / filename attacks | UUID object keys; original filename stored for display only, never used as a path |
| Secrets | All via env vars (`.env.example` committed, `.env` gitignored); no secrets in code or compose |
| Submission spam | Rate limiting + honeypot field on the public form (invisible to humans, catnip for bots) |
| Email bombing via form | One confirmation per submission, ever; notifications go to a fixed internal list |

---

## 14. Local Development Environment

`docker-compose.yml` brings up the **entire stack** with one command:

| Service | Image | Port |
|---|---|---|
| `postgres` | `postgres:16` | 5432 |
| `minio` | `minio/minio` | 9000 (API) / 9001 (console) |
| `mailpit` | `axllent/mailpit` | 8025 (web inbox) / 1025 (SMTP) |
| `api` | built from `apps/api/Dockerfile` | 8000 (docs at `/docs`) |
| `web` | built from `apps/web/Dockerfile` | 3000 |
| `migrate` | one-shot `node:22-slim` + `npm ci` (locked Prisma 7): `prisma migrate deploy` + seed attorney | exits 0 |

```bash
git clone <repo> && cd alma-leads
cp .env.example .env
docker compose up --build
# → public form:      http://localhost:3000
# → internal login:   http://localhost:3000/login  (attorney@example.com / password123)
# → leads dashboard:  http://localhost:3000/leads
# → email inbox:      http://localhost:8025
# → API docs:         http://localhost:8000/docs  (direct; the app itself calls the API via :3000/api)
```

Notes:

- The **migrate container is a gate**: `api` waits on it (`depends_on: condition: service_completed_successfully`), so the schema is always applied before the app accepts traffic. Node exists only in this one-shot image and the dev toolchain — never in the API runtime image.
- **Postgres init script** (`docker/postgres/init.sql`, mounted into `/docker-entrypoint-initdb.d`) creates `alma_shadow` alongside `alma`. `.env.example` sets `DATABASE_URL`, `SHADOW_DATABASE_URL`, `ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000`, `COOKIE_SECURE=false`, `SESSION_COOKIE_NAME=session`, and `API_INTERNAL_URL=http://api:8000` (the `web` build arg and runtime env).
- **API image build (uv, multi-stage).** The build stage installs locked, non-dev dependencies into `/app/.venv`. The runtime stage copies only that venv and the app code, so neither uv nor dev tools ship:

```dockerfile
# apps/api/Dockerfile
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev
COPY app ./app

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 api
WORKDIR /app
COPY --from=build --chown=api:api /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER api
EXPOSE 8000
# FORWARDED_ALLOW_IPS (the web service address) comes from compose/env
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

  Dependency layers rebuild only when `uv.lock` or `pyproject.toml` changes; editing `app/` reuses the cached venv layer. Both stages use the same `python:3.12-slim` base, so the venv's interpreter path is valid in the runtime stage (`UV_PYTHON_DOWNLOADS=0` keeps uv on the image's Python).
- `Makefile` wraps the common loop: `make up`, `make down`, `make test`, `make lint`, `make generate-client`, `make migrate-dev name=…`, `make db-check`.
- No cloud credentials needed for a full local demo — Mailpit and MinIO are the stand-ins for Resend and S3.

---

## 15. Testing Strategy

**API (pytest, async):**

- **Unit:** state machine transitions (valid, invalid → 409), validation edge cases (oversized file, bad MIME, long names, bad email), `EmailSender` adapters against fakes.
- **Integration:** full request cycle with a real Postgres (docker-compose or testcontainers), fake sender asserting both `EmailLog` rows + email payloads; auth flow (login → cookie → guarded route → logout → 401); Origin check (missing `Origin`, foreign `Origin`, `Sec-Fetch-Site: cross-site` → 403 on `PATCH`, login, logout; the test client sends `Origin: http://localhost:3000` by default); forwarded-IP rate-limit buckets; resume upload → presigned download round-trip against MinIO.
- **Contract:** FastAPI's OpenAPI snapshot test — fails CI if the schema changes without the web client being regenerated.
- **Schema drift:** `scripts/db-check.sh` in its own CI job — `prisma migrate diff` (migrations ↔ schema, via the shadow DB; migrated DB ↔ schema) and the `compare_metadata` test (migrated DB ↔ SQLAlchemy models) — see [§5](#drift-protection).
**Web (Vitest + Testing Library):**
- Form validation parity with API rules (same edge cases), file-input constraints, transition-button optimistic rollback behavior.


---

## 16. Key Trade-offs & Upgrade Paths

Honest record of where this design draws lines, and which way each scales:

| Area | Now | At Scale |
|---|---|---|
| Data layer | Prisma schema/migrations + hand-mapped SQLAlchemy models, drift-checked in CI | If the Prisma requirement lifts: Alembic autogenerate from the SQLAlchemy models, delete `prisma/` and Node from the toolchain — runtime query code unchanged |
| Email dispatch | In-process `BackgroundTasks` + audit log | Redis/arq or SQS + worker; same `send_lead_emails()` body, new transport |
| Auth | Own JWT cookie, seeded users | Managed IdP (Auth0/Cognito); swap `get_current_attorney` internals, routes unchanged |
| File scanning | Size + extension + MIME sniffing | ClamAV sidecar in compose; binary gate in the upload path |
| Storage | MinIO (S3 API) | Real S3 via `S3_ENDPOINT` env var; zero code change |
| Email provider | SMTP→Mailpit / Resend adapters | New adapters behind the protocol |
| Lead list | Offset pagination, newest first | Cursor pagination (`createdAt` + id tiebreak) |
| Rate limiting | In-process per-IP | Redis-backed shared limiter once there are >1 API replicas |
| Attorney routing | Fixed `ATTORNEY_EMAILS` list | `User` table already exists — assignment is a nullable FK + a routing policy |
| Resume format checks | PDF/DOC/DOCX | Extract text for search/dedupe (PyMuPDF/textract pipeline) |

The recurring theme: **every integration point is an interface (`EmailSender`, S3-compatible storage, OpenAPI-generated client, Prisma-owned schema with drift-checked SQLAlchemy models)** — so scale changes are configuration and adapter swaps, not rewrites.
