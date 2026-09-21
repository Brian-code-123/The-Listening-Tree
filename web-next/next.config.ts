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
  async rewrites() {
    const target = process.env.E2E_API_PROXY;
    if (!target) return [];
    return API_PATHS.map((source) => ({ source, destination: `${target}${source}` }));
  },
};

export default nextConfig;
