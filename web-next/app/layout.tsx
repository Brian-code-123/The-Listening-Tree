import type { Metadata, Viewport } from "next";
import { Inter, Noto_Sans_HK } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
// Self-hosted (bundled into our own CSS/assets) instead of CDN <link>s: a
// cross-origin stylesheet in <head> blocks first paint, and the web-font swap
// it triggered pushed the login page's CLS over the "good" threshold. Only the
// core + solid + brands sheets are needed (no regular/v4-compat), and the same
// 6.4.0 release as the CDN link this replaces, so every icon renders as before.
import "@fortawesome/fontawesome-free/css/fontawesome.min.css";
import "@fortawesome/fontawesome-free/css/solid.min.css";
import "@fortawesome/fontawesome-free/css/brands.min.css";
import "./globals.css";
import ReminderAlarm from "./components/ReminderAlarm";

// next/font self-hosts the files at build time and emits a size-adjusted
// fallback face, so the swap from system font to web font doesn't shift layout.
// Noto Sans HK ships hundreds of CJK slices; the browser only fetches the
// unicode-range slices a page actually uses, and none are preloaded.
const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-inter" });
const notoSansHK = Noto_Sans_HK({ subsets: ["latin"], display: "swap", variable: "--font-noto-sans-hk", preload: false });

export const metadata: Metadata = {
  title: "The Listening Tree",
  description: "Next.js pages for The Listening Tree — see docs/FRONTEND_ROADMAP.md for migration status.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

// Build-time constant (Next.js inlines NEXT_PUBLIC_* vars even in a server
// component like this layout) — same value app/lib/api.ts's API_BASE
// resolves to at runtime, used here just for the static asset URL below.
const STATIC_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${notoSansHK.variable}`}>
      <head>
        {/* The backend's own TTS voice-selection logic (Cantonese-voice
            scoring heuristics) — loaded from the backend rather than
            reimplemented, so /accessibility and /chat's "read aloud"
            behavior stays byte-identical to the Jinja pages instead of
            risking a subtly different port. */}
        <script src={`${STATIC_BASE}/static/speech.js`} defer />
      </head>
      <body>
        {children}
        <ReminderAlarm />
        <Analytics />
      </body>
    </html>
  );
}
