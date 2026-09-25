-- Runs once, on first start of an empty data volume.
-- alma_shadow: Prisma's shadow DB (migrate dev / migrate diff --from-migrations). Wiped on use.
-- alma_test:   pytest's throwaway DB (tests rebuild it from prisma/migrations on every run).
-- alma_ci:     `make db-check` target (recreated empty on every run).
CREATE DATABASE alma_shadow;
CREATE DATABASE alma_test;
CREATE DATABASE alma_ci;
