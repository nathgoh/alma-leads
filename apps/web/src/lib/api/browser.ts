// Client components only. Relative /api/v1/... URLs go through the same-origin NextJS rewrite,
// so the browser attaches the httpOnly session cookie and the Origin header the API requires.
import createClient, { type Middleware } from "openapi-fetch";

import { loginUrl } from "./config";
import type { paths } from "./schema";

const redirectOn401: Middleware = {
  async onResponse({ request, response }) {
    const isLogin = new URL(request.url).pathname.endsWith("/auth/login");
    if (response.status === 401 && !isLogin && typeof window !== "undefined") {
      window.location.assign(loginUrl(window.location.pathname + window.location.search));
    }
    return response;
  },
};

export const browserApi = createClient<paths>({
  baseUrl: typeof window === "undefined" ? "http://localhost" : window.location.origin,
  credentials: "same-origin",
  fetch: (request) => globalThis.fetch(request), // resolved per call (lets tests stub fetch)
});
browserApi.use(redirectOn401);
