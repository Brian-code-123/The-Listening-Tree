import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Silences Turbopack's workspace-root auto-detection warning — the repo
  // root has its own package-lock.json (for the FastAPI app's Playwright/
  // Vitest tooling), which Turbopack otherwise mistakes for this app's
  // workspace root.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
