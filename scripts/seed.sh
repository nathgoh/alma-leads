#!/usr/bin/env bash
# Seed attorney accounts (idempotent). docker compose runs this automatically on api start;
# use this when running the API on the host.
set -euo pipefail
cd "$(dirname "$0")/../apps/api"
uv run python -m app.seed
