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
TEST_DATABASE_URL="$DATABASE_URL" USE_PRISMA_MIGRATED_DB=1 \
  uv run --locked pytest tests/test_schema_drift.py
