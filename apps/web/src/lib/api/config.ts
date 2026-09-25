// Session cookie name: `session` over http in dev, `__Host-session` in production (HTTPS).
export const SESSION_COOKIE = process.env.SESSION_COOKIE_NAME ?? "session";

/** Only same-site relative paths are valid post-login destinations (no open redirects). */
export function safeNextPath(next: string | null | undefined, fallback = "/leads"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return fallback;
  return next;
}

export function loginUrl(next: string): string {
  return `/login?next=${encodeURIComponent(next)}`;
}
