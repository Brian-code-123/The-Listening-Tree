# web-next — Next.js proof of concept for `/history`

Local-dev-only proof of concept for the Jinja2+jQuery → Next.js migration
described in [`../docs/FRONTEND_ROADMAP.md`](../docs/FRONTEND_ROADMAP.md)
(Stage 2). It reimplements the existing `/history` conversation-history
page against the real backend API — no mocking — to validate the
architecture (routing, data fetching, component structure) before
committing to migrating anything else. The existing Jinja `/history` page
at `templates/conversation_history.html` is untouched and keeps working
exactly as it does today; this runs alongside it, not instead of it.

**Not deployed.** Making this live would need `vercel.json` restructured
into a multi-builder config (currently a single catch-all routing
everything to the Python function) and — since Vercel projects on
different `*.vercel.app` subdomains are different sites for cookie
purposes, and this project has no custom domain to share a cookie domain
across two deployments — a real plan for how auth works across two
separately-deployed apps. Both are real, solvable problems, just
deliberately out of scope for a local proof of concept.

## Running it

1. Start the backend first, from the repo root: `python run.py` (port 5000).
2. Log in normally at `http://localhost:5000/login` in your browser.
3. From this directory: `npm install && npm run dev` (port 3001).
4. Open `http://localhost:3001/history`.

Step 2 matters: this app has no login page of its own. It relies on the
`lt_session` cookie already being set in your browser from step 2 —
`localhost` cookies are host-scoped without a port component, so the
cookie set while on `localhost:5000` is also sent along with this app's
`credentials: 'include'` fetches to `localhost:5000` from `localhost:3001`.
If you see a fetch error mentioning the backend, you're probably not
logged in at `localhost:5000` yet.

## What's ported vs. what isn't

- Ported: list/filter/pin/rename/tag, exactly matching the existing
  backend routes (`GET /conversations`, `POST /conversations/{id}/pin`,
  `/title`, `/tag`) and the same request/response shapes.
- Styling: plain CSS in `app/globals.css`, hand-ported from the relevant
  subset of `../static/style.css` (design tokens + the page-specific rules
  from `conversation_history.html`'s inline `<style>` block) — not
  Tailwind, deliberately, to keep this POC's validation scope to the
  frontend architecture itself. See the SDLC plan for why.
- `CONVERSATION_TAGS` (icon/color per tag) is duplicated in
  `app/lib/translations.ts` from `../app/core/config.py` — it's a small,
  fixed design constant, not worth a second backend endpoint for. Keep the
  two in sync by hand if that set ever changes.
- Translations come from a new backend endpoint, `GET /translations/{lang}`
  (added to `app/routers/pages.py` — the only backend change beyond a CORS
  allowlist entry and one unrelated found-bug fix, see the SDLC plan for
  both), rather than being duplicated by hand.
- Language switching isn't implemented in this POC (English only) — the
  existing page's `/set_language/{lang}` redirect flow is designed around
  full-page navigation, which doesn't fit a client-rendered SPA page
  cleanly; solving that properly belongs to whichever later stage actually
  replaces this page in production, not this proof of concept.
