# web-next — Next.js `/history` (production)

Started as a local-only proof of concept for the Jinja2+jQuery → Next.js
migration described in
[`../docs/FRONTEND_ROADMAP.md`](../docs/FRONTEND_ROADMAP.md) (Stage 2),
now deployed to production as a second Vercel `service` alongside the
FastAPI app — see `vercel.json` at the repo root. Both services sit behind
the same `the-listening-tree.vercel.app` origin, routed by path (`/history`
and `/_next/*` go to this app, everything else to the Python one), so the
`lt_session` session cookie works the same way it always has — no
cross-origin auth workaround needed in production. It reimplements the
`/history` conversation-history page against the real backend API — no
mocking. The old Jinja `/history` route/template
(`templates/conversation_history.html`) is left in place but no longer
reachable once the `services` rewrite is live, since `GET /history` now
resolves to this app instead — see the SDLC plan for why it wasn't deleted
in the same pass as this deployment.

## Running it locally

1. Start the backend first, from the repo root: `python run.py` (port 5000).
2. Log in normally at `http://localhost:5000/login` in your browser.
3. From this directory: `npm install && npm run dev` (port 3001).
4. Open `http://localhost:3001/history`.

Locally the two apps are still separate dev servers on different ports —
`web-next/.env.local` (gitignored) sets `NEXT_PUBLIC_API_BASE=http://localhost:5000`
so this app's fetches/links point at the right place; in production that
variable is unset, which makes `API_BASE` an empty string and every
request/link resolve same-origin instead. Step 2 above matters locally:
this app has no login page of its own, and relies on the `lt_session`
cookie already being set in your browser — `localhost` cookies are
host-scoped without a port component, so the cookie set on `localhost:5000`
is also sent along with this app's `credentials: 'include'` fetches from
`localhost:3001`. If you see a fetch error mentioning the backend, you're
probably not logged in at `localhost:5000` yet.

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
