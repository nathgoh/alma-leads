// Run the Prisma CLI from apps/api so npx finds this file.
import { config } from "dotenv";
import { defineConfig, env } from "prisma/config";

// Prisma 7 does not load .env on its own. Real env vars win; then the monorepo-root .env.
config({ path: ["../../.env", ".env"], quiet: true });

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
