import type { NextConfig } from "next";
import path from "path";

// Backend paths that vercel.json sends to the API service. Only proxied when
// E2E_API_PROXY is set, so tests run same-origin like production; a normal
// dev/prod build is unaffected.
const API_PATHS = [
  "/auth/:path*", "/me", "/config", "/translations/:lang", "/health",
  "/conversations", "/conversations/:path*", "/reminders", "/reminders/:path*",
  "/get_response", "/get_chat_history", "/get_reminders", "/get_news",
  "/get_hk_holidays", "/get_hk_guide", "/transcribe", "/static/:path*",
  "/set_language/:lang", "/logout", "/send_verification_code",
  "/profile/name", "/profile/password",
];

// Mirrors app/core/security_headers.py (tests/test_security_headers.py keeps the
// two identical). Pages are prerendered, so a nonce-based CSP is not possible and
// scripts need 'unsafe-inline'; see that file for the trade-off. The policy is
// production-only and report-only until CSP_ENFORCE=1.
const SECURITY_HEADERS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "microphone=(self), camera=(), geolocation=(), payment=()" },
];
const CSP =
  "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; " +
  "img-src 'self' data: blob:; media-src 'self' blob: data:; font-src 'self' data:; connect-src 'self'; " +
  "frame-ancestors 'none'; form-action 'self'; base-uri 'self'; object-src 'none'";

const nextConfig: NextConfig = {
  // Silences Turbopack's workspace-root auto-detection warning — the repo
  // root has its own package-lock.json (for the FastAPI app's Playwright/
  // Vitest tooling), which Turbopack otherwise mistakes for this app's
  // workspace root.
  turbopack: {
    root: path.join(__dirname),
  },
  // Playwright reaches the dev server as 127.0.0.1; Next's dev server refuses
  // /_next/* (including the HMR websocket that hydration waits on) from origins
  // it doesn't recognize.
  allowedDevOrigins: process.env.E2E_API_PROXY ? ["127.0.0.1"] : [],
  async headers() {
    const list = [...SECURITY_HEADERS];
    if (process.env.NODE_ENV === "production") {
      const name = process.env.CSP_ENFORCE === "1" ? "Content-Security-Policy" : "Content-Security-Policy-Report-Only";
      list.push({ key: name, value: CSP });
    }
    return [{ source: "/:path*", headers: list }];
  },
  async rewrites() {
    const target = process.env.E2E_API_PROXY;
    if (!target) return [];
    return API_PATHS.map((source) => ({ source, destination: `${target}${source}` }));
  },
};

export default nextConfig;
