import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "The Listening Tree",
  description: "Next.js pages for The Listening Tree — see docs/FRONTEND_ROADMAP.md for migration status.",
};

// Build-time constant (Next.js inlines NEXT_PUBLIC_* vars even in a server
// component like this layout) — same value app/lib/api.ts's API_BASE
// resolves to at runtime, used here just for the static asset URL below.
const STATIC_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <head>
        {/* Font Awesome + Google Fonts, same CDN sources the main app uses
            (templates/conversation_history.html) — kept as CDN links here
            rather than an npm icon package or next/font, to match the
            "reimplementation, not a redesign" scope of this migration.
            `next lint` warns with @next/next/no-page-custom-font (a Pages
            Router-era rule about per-page <Head>s) even though this is the
            App Router's root layout — the correct place for a site-wide
            font link — so the warning is expected and non-blocking. */}
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+HK:wght@400;500;600;700&display=swap" rel="stylesheet" />
        {/* The backend's own TTS voice-selection logic (Cantonese-voice
            scoring heuristics) — loaded from the backend rather than
            reimplemented, so /accessibility and /chat's "read aloud"
            behavior stays byte-identical to the Jinja pages instead of
            risking a subtly different port. */}
        <script src={`${STATIC_BASE}/static/speech.js`} defer />
      </head>
      <body>{children}</body>
    </html>
  );
}
