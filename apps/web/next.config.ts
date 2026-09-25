import type { NextConfig } from "next";

// Where FastAPI lives on the server side. Rewrites are resolved at `next build`, so in Docker this
// is passed as a build arg (http://api:8000); locally it defaults to the host-side API.
const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    // The browser only ever talks to this origin: /api/* is proxied to FastAPI byte-for-byte
    // (multipart uploads and Set-Cookie included). No CORS anywhere.
    return [{ source: "/api/:path*", destination: `${apiInternalUrl}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
