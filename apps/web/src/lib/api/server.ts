// Server components only (reads). Calls FastAPI directly on the internal network and forwards
// just the session cookie from the incoming request. All writes go through `browserApi`.
import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import createClient from "openapi-fetch";

import { SESSION_COOKIE, loginUrl } from "./config";
import type { paths } from "./schema";

export async function serverApi() {
  const session = (await cookies()).get(SESSION_COOKIE);
  return createClient<paths>({
    baseUrl: process.env.API_INTERNAL_URL ?? "http://localhost:8000", // never sent to the browser
    headers: session ? { cookie: `${SESSION_COOKIE}=${session.value}` } : {},
    cache: "no-store", // per-user data: never cache across requests
  });
}

/** Unwrap an openapi-fetch result in a server component: 401 → /login?next=…, other errors throw. */
export function unwrap<T>(
  result: { data?: T; error?: unknown; response: Response },
  currentPath: string,
): T {
  if (result.response.status === 401) redirect(loginUrl(currentPath));
  if (result.data === undefined) {
    throw new Error(`API ${result.response.status}: ${JSON.stringify(result.error)}`);
  }
  return result.data;
}
