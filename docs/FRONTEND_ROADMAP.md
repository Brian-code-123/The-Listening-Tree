# Frontend Modernization Roadmap

Status: **not started, no timeline** — written up so there's a concrete
answer for "what's next" (FYP follow-up, portfolio conversations) without
committing to a rewrite before the current build is stable and graded.

The current frontend is server-rendered Jinja2 templates (`templates/`)
with jQuery for interactivity, plus a thin Capacitor shell (`www/`) that
just loads the deployed web app inside a native WebView. This works and is
appropriate for a solo student project on a deadline, but doesn't reflect
current industry-standard frontend tooling (component frameworks, typed
frontend code, client-side routing).

## Why not now

Migrating the frontend against the current single-file `run.py` backend
would mean redoing the integration work twice: once now, and again after
the backend modularization (see main [`REQUIREMENTS.md`](./REQUIREMENTS.md)
and the project plan) gives each feature area a clean router and, ideally,
a JSON API rather than server-rendered HTML. The backend split is the
prerequisite, not a parallel track.

## Staged plan, once undertaken

1. **Stage 0 (prerequisite)** — Finish the backend modularization
   (`app/routers/*`, `app/services/*`) and the Alembic migration setup
   first. A stable, versioned REST surface is what makes a decoupled
   frontend viable at all.
2. **Stage 1** — Convert routes that currently return `TemplateResponse`
   into a clean JSON API, keeping the Jinja templates rendering in parallel
   as a fallback during the transition (so the app never has a broken
   in-between state).
3. **Stage 2** — Stand up a Next.js app consuming that API, one page at a
   time. Start with `/history` (the conversation history page) as the
   proof of concept: it's the newest, smallest, and most naturally
   component-shaped of the existing pages (a filter bar + a list of
   cards), and lowest-risk to get wrong.
4. **Stage 3** — Migrate `/login`, `/register`, `/profile`,
   `/accessibility`, `/hk_guide`, in roughly ascending order of complexity,
   once the pattern from Stage 2 is proven.
5. **Stage 4** — Migrate `/chat` last. It's the largest and highest-risk
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
