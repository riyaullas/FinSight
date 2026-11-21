import type { NextConfig } from "next";

// In development the Next server proxies /api to the local backend so the browser talks to a
// single origin (cookies stay SameSite=Strict, no CORS). In production the reverse proxy
// (deploy/Caddyfile) routes /api directly to the backend.
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
