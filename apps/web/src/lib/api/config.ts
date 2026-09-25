// Session cookie name: `session` over http in dev, `__Host-session` in production (HTTPS).
export const SESSION_COOKIE = process.env.SESSION_COOKIE_NAME ?? "session";

/** Only same-site relative paths are valid post-login destinations (no open redirects). */
export function safeNextPath(next: string | null | undefined, fallback = "/leads"): string {
  if (!next || !next.startsWith("/")) return fallback;
  // Resolve against a throwaway origin and keep only same-origin paths. The old string-prefix
  // checks missed that WHATWG strips leading control characters (`/\t/evil.example` → host
  // `evil.example`), turning `next` into an off-site redirect.
  let url: URL;
  try {
    url = new URL(next, "http://same-origin.invalid");
  } catch {
    return fallback;
  }
  if (url.origin !== "http://same-origin.invalid") return fallback;
  return `${url.pathname}${url.search}${url.hash}`;
}

export function loginUrl(next: string): string {
  return `/login?next=${encodeURIComponent(next)}`;
}
