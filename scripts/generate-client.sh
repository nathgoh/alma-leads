#!/usr/bin/env bash
# Regenerate the web client from the API's OpenAPI schema (the contract).
# tests/test_openapi_contract.py fails until this has been run after an API change.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
(cd "$root/apps/api" && uv run python -m app.openapi_dump > "$root/apps/web/openapi.json")
(cd "$root/apps/web" && pnpm generate:api)
