# Frontend Modernization Roadmap

Status: **all stages complete.** Every page is now served by the Next.js
app in `web-next/` (App Router, TypeScript). The Jinja templates in
`templates/` and their FastAPI routes are still in the repo, still
working, and deliberately left in place until the migrated pages have
proven stable in production — deleting them is the final cleanup step,
not part of the migration itself.

The original frontend was server-rendered Jinja2 templates with jQuery
for interactivity, plus a thin Capacitor shell (`www/`) that loads the
deployed web app inside a native WebView. That was appropriate for a solo
student project on a deadline, but didn't reflect current frontend
tooling (component frameworks, typed frontend code, client-side routing).

## Why it waited for the backend split

Migrating against the old single-file `run.py` backend would have meant
doing the integration work twice: once then, and again after the backend
modularization (see [`REQUIREMENTS.md`](./REQUIREMENTS.md)) gave each
feature area a clean router and a JSON API rather than server-rendered
HTML. The backend split was the prerequisite, not a parallel track — and
it's what made the migration below a page-by-page port rather than a
rewrite.

## How the two apps are deployed together

Both run as Vercel `services` behind a single origin, configured in
`vercel.json`: page routes rewrite to the `web` service (`web-next/`),
everything else falls through to the `api` service (FastAPI). Same origin
means the session cookie just works — no CORS setup, no cross-origin
cookie problems, no second domain. Locally the two are separate dev
servers, which is what `NEXT_PUBLIC_API_BASE` exists to bridge.

## The staged plan, as executed

1. **Stage 0 (prerequisite)** — *(done)* Finish the backend modularization
   (`app/routers/*`, `app/services/*`) and the Alembic migration setup
   first. A stable, versioned REST surface is what makes a decoupled
   frontend viable at all.
2. **Stage 1** — *(done)* Convert routes that currently return `TemplateResponse`
   into a clean JSON API, keeping the Jinja templates rendering in parallel
   as a fallback during the transition (so the app never has a broken
   in-between state).
3. **Stage 2** — *(done)* Stand up a Next.js app consuming that API, one page at a
   time. Start with `/history` (the conversation history page) as the
   proof of concept: it's the newest, smallest, and most naturally
   component-shaped of the existing pages (a filter bar + a list of
   cards), and lowest-risk to get wrong.
4. **Stage 3** — *(done)* Migrate `/login`, `/register`, `/profile`,
   `/accessibility`, `/hk_guide`, in roughly ascending order of complexity,
   once the pattern from Stage 2 is proven.
5. **Stage 4** — *(done)* Migrate `/chat` last. It's the largest and highest-risk
   page: voice I/O (Web Speech API + `/transcribe` fallback), the
   reminder-alarm polling loop, and the main conversational UI all live
   here. Only attempt this once the simpler pages have validated the
   approach.

## Mobile build implications

At every stage, the Capacitor native app (`capacitor.config.ts`) continues
to just load the deployed web URL inside a WebView — this holds whether
that URL serves Jinja-rendered HTML or a Next.js app. No native
iOS/Android code changes are required by this migration; it's purely a web
frontend change from the native shell's point of view.
