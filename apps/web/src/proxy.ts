// Next 16 renamed middleware.ts → proxy.ts. UX only: redirects page requests without a session
// cookie to /login. The API is the security boundary. Matches pages only — never /api/*, so
// proxied API calls and uploads pass through untouched.
import { type NextRequest, NextResponse } from "next/server";

import { SESSION_COOKIE, loginUrl } from "@/lib/api/config";

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (!request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.redirect(new URL(loginUrl(pathname + search), request.url));
  }
  // Let server components know where they are, for /login?next=… when the session has expired.
  const headers = new Headers(request.headers);
  headers.set("x-pathname", pathname + search);
  return NextResponse.next({ request: { headers } });
}

export const config = { matcher: ["/leads", "/leads/:path*"] };
