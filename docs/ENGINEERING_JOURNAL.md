# Engineering Journal: from FYP submission to a maintained system

This documents a specific stretch of work on this project: a senior
engineer reviewed the codebase as it stood after the initial FYP build,
and the entries below are what changed in response, and — more
importantly — why. The point isn't to list diffs (`git log` already does
that); it's to make the reasoning behind each decision legible to someone
who wasn't in the room, since that reasoning is the actual skill being
demonstrated.

## Where it started

The review's headline finding: security and testing discipline (password
hashing, account lockout, CI running real integration tests against a
live Postgres container) were already ahead of typical student-project
work, but the codebase itself was a single 3,384-line `run.py` — routes,
database schema, LLM calls, and email sending all interleaved in one
file, with no database migration tool, no rate limiting, and no written
requirements. The honest read of that: the *discipline* was there, the
*structure* wasn't.

## Splitting the monolith

`run.py` became `app/routers/`, `app/services/`, `app/db/`, and
`app/core/` — auth, chat, reminders, conversations, and HK-guide routes
each in their own router; the AI/email/transcription integrations each in
their own service module; the asyncpg pool and query helpers isolated
from the schema definitions. Mechanically this was straightforward — move
functions, fix imports, wire `include_router()` calls — but it's the
prerequisite everything else in this journal depends on. A rate limiter
that needs its own table, a migration tool that needs its own schema
module, a second frontend that needs a stable API surface — none of those
have a natural home in a 3,000-line file. The split isn't the improvement
itself; it's what makes the rest of the improvements *possible* to reason
about individually instead of as edits to one sprawling module.

## Alembic, and why the baseline isn't a fresh `CREATE`

The schema had been managed entirely as `CREATE TABLE IF NOT EXISTS` /
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, re-run on every process start
— idempotent, but with no version history and no rollback path. Wiring up
Alembic is the obvious fix, but the detail that mattered in practice: the
production database already has this schema, live, with real user data.
The first migration doesn't create anything — it's a baseline stamped
onto the existing database (`alembic stamp`, not `alembic upgrade` from
empty), generated to mirror the current schema exactly and diffed against
the live schema before ever touching production. Get that step wrong and
either the migration tries to re-create tables that already exist, or
Alembic's own bookkeeping (`alembic_version`) silently disagrees with
reality from day one.

The other detail: migrations run through a synchronous `psycopg2`
connection, not the app's runtime `asyncpg` pool. Two independent reasons
converged on that choice — the direct (non-pooler) `DATABASE_URL` turned
out to be IPv6-only and unreachable from the network this was built on,
and `asyncpg` has its own documented SSL-negotiation hang against
Supabase's connection pooler that `psycopg2` simply doesn't share. A
migration is a rare, deliberate, blocking operation — a synchronous
connection is the right tool for that, not a compromise.

## The rate limiter: why not `slowapi`'s default, why not Redis

`/login`, `/register`, `/send_verification_code`, and `/transcribe` had no
abuse protection beyond login's existing account lockout. `slowapi` is
the obvious FastAPI-ecosystem choice, and its default storage is an
in-process Python `dict`. That's the detail that mattered: this app
deploys as a Vercel serverless function. Separate invocations — different
cold starts, genuinely concurrent requests — do not share process memory.
An in-memory counter on serverless doesn't enforce a limit across
instances; it enforces a limit *per instance*, which for a bursty
attacker or just an unlucky sequence of cold starts is not the same
guarantee at all. Shipping that and calling it "rate limited" would have
been the kind of thing that looks correct in a local test and quietly
isn't true in production — worse than not having the reasoning written
down anywhere.

The fix isn't Redis. Redis is the standard answer for a
higher-traffic production system, but it's a new external service, a new
secret to provision and track, and a new failure mode, for an app whose
actual traffic doesn't need it yet. The app already has a database it
depends on for everything else, so the limiter is a small Postgres table
and one atomic statement:

```sql
INSERT INTO rate_limit_events (key, window_start, count)
VALUES ($1, $2, 1)
ON CONFLICT (key, window_start)
DO UPDATE SET count = rate_limit_events.count + 1
RETURNING count
```

Atomic matters specifically because the naive version — `SELECT count`,
compare in Python, `UPDATE` — has a real race: two concurrent requests can
both read count=9, both decide they're under a limit of 10, and both
write, letting the count reach 11. The `INSERT ... ON CONFLICT ...
RETURNING` form does the increment and the read as one indivisible
operation, so the caller only ever sees the count *after* it's already
been incremented — there's no window for two requests to both act on a
stale read.

Old rows get swept by the same periodic background task that already
existed for reminder checks, rather than a new cron — one more place
where reusing infrastructure that already existed beat adding a new
moving part.

## The Next.js migration: a local POC before any production change

The existing frontend is server-rendered Jinja2 templates with jQuery —
functional, but not what current frontend hiring conversations expect to
see. Rather than committing to a full rewrite, the plan was staged: prove
the *pattern* works on the smallest, newest page (`/history`, conversation
history) before touching anything else, and prove it **locally, against
the real backend API, with no mocking**, before it goes anywhere near the
live deployment.

That staging turned out to matter almost immediately. The naive
assumption was that a separately-deployed Next.js app would need to solve
cross-origin session cookies — a real, nontrivial problem, since two
different `*.vercel.app` project subdomains are different sites as far as
a browser's cookie jar is concerned, and this project has no custom
domain to share a cookie scope across two separate deployments. Digging
into Vercel's current platform docs surfaced a cleaner answer: `services`
+ `rewrites` in `vercel.json` — Vercel's supported way to run multiple
frameworks (a Python app and a Next.js app, in this case) as separate
services *within the same project*, routed by path, under the *same*
origin. Same origin means the existing session cookie just works, with no
cross-origin workaround needed at all in production — only the local dev
setup (where the two really are on different ports, `5000` and `3001`)
needs `credentials: 'include'` and an explicit CORS allowlist entry, and
that stays exactly what it is: a local development convenience, not
something the deployed app depends on.

Even with that answer in hand, it went to a preview deployment first, not
directly to `main` — the `services`/`rewrites` config is new enough, and
its plan-tier requirements undocumented enough, that trusting it against
a live app on the strength of reading the docs alone would have been the
wrong risk to take. The preview build succeeded (both the Python and
Node.js functions built cleanly), and — once past Vercel's own
SSO-protected preview-URL wall, which is a separate, expected layer
unrelated to this app's own auth — a real registered test account
confirmed the session cookie, conversation list, pin/rename/tag
interactions, and the link back into the existing chat page all worked
exactly as they had locally. Only then did it merge to `main`.

## What's still not enterprise-grade

Naming these honestly, rather than letting the diffs speak past them:

- **The rate limiter has no load test.** The reasoning behind the
  atomic-counter design is sound, but "sound reasoning" and "verified
  under real concurrent load" are different claims, and only the first
  one is currently true.
- **Only one page migrated to Next.js.** `/history` was deliberately the
  easiest page to prove the pattern on — small, newest, most
  component-shaped. `/chat`, the largest and highest-risk page (voice
  I/O, the reminder-alarm polling loop), is explicitly last in the
  staged plan, and hasn't been started.
- **The old Jinja `/history` route is dead code, not deleted.** Once the
  `services` rewrite is live, `GET /history` never reaches the FastAPI
  route anymore — but the route and template are still sitting in the
  codebase. Low-risk to remove, just not done in the same pass as the
  deployment that made it unreachable, on the principle of not bundling
  an infra change with a cleanup change in one commit.
- **No formalized SLA or on-call story.** This is a personal project with
  a real live deployment, not a team-operated production system — there's
  no expectation of paged incident response, and pretending otherwise
  would be dishonest, not thorough.

None of these are hidden gaps — they're the actual next items on the
project's own roadmap docs (`docs/FRONTEND_ROADMAP.md`, the SDLC plan this
journal follows), which is the point: a system's maturity shows as much
in what it says it *hasn't* done yet as in what it has.
