# Common local commands. Most are thin wrappers over uv / pnpm / docker compose.
SHELL := /bin/bash
-include .env
export

PG_ADMIN_URL := postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:$(POSTGRES_HOST_PORT)

.PHONY: help up down logs services test test-api test-web lint generate-client migrate-dev db-check seed

help:
	@grep -E '^[a-z-]+:' Makefile | cut -d: -f1 | sort | tr '\n' ' '; echo

up:            ## whole stack: http://localhost:3000
	docker compose up --build -d --wait
	@echo "form :3000  dashboard :3000/leads  mail :8025  api docs :8000/docs  minio :9001"

down:
	docker compose down

logs:
	docker compose logs -f api web

services:      ## just the backing stores (for running api/web on the host)
	docker compose up -d --wait postgres minio mailpit

test: test-api test-web

test-api: services
	cd apps/api && uv run pytest

test-web:
	cd apps/web && pnpm test

lint:
	cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd apps/web && pnpm typecheck

generate-client:
	scripts/generate-client.sh

migrate-dev:   ## make migrate-dev name=add_something
	@test -n "$(name)" || (echo "usage: make migrate-dev name=<change>" && exit 1)
	cd apps/api && npx prisma migrate dev --name $(name)

db-check: services   ## drift checks against a freshly recreated alma_ci + alma_shadow
	docker compose exec -T postgres psql -U $(POSTGRES_USER) -q \
	  -c 'DROP DATABASE IF EXISTS alma_ci WITH (FORCE)' -c 'CREATE DATABASE alma_ci'
	DATABASE_URL=$(PG_ADMIN_URL)/alma_ci SHADOW_DATABASE_URL=$(PG_ADMIN_URL)/alma_shadow scripts/db-check.sh

seed:
	scripts/seed.sh
