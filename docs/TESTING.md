# Test Plan and Report

This document covers the test plan, strategy, criteria, deliverables and results for
The Listening Tree after the move from Jinja templates to the Next.js front end. Every
number below comes from a run recorded on 2026-09-22 (environment in section 9); where a
result is not yet available (for example the first CI run) it says so.

## 1. Testing Strategy

The suite tests the system the way a user meets it: through the browser, against the same
application layout that production uses.

| Layer | Tool | What it proves |
|---|---|---|
| Black-box / end-to-end | Playwright | User flows through the real UI on 4 browser/device projects |
| API integration | pytest against a live local PostgreSQL | Endpoint contracts, ownership rules, data effects |
| Backend unit | pytest with a mocked database | Core flows without a database |
| Component / hook unit | Vitest (jsdom, Testing Library) | Language hooks, loading screen, delete-confirm flow, translation parity |
| Stress | k6 | Latency and error rate under concurrent load |

Design decisions that make the results trustworthy and repeatable:

- **Same-origin, like production.** Production routes pages to Next.js and API paths to
  FastAPI under one origin (`vercel.json`). The e2e run starts both servers and lets Next
  proxy the API paths, so login redirects, cookies and language switching behave as they do
  in production. (One difference: the proxy rewrites the `Host` header, so the backend's
  "return to the page you were on" redirect falls back to `/`; production keeps the host.)
- **Hermetic.** Tests use their own database (`listening_tree_e2e`) and blank every
  third-party credential (LLM, news, speech-to-text, email, Google). Chat replies therefore
  come from the built-in fallback and a run costs nothing. The runner refuses any database
  host that is not local before a server starts, and unit tests pin that guard against the
  real production host patterns. All non-local network requests are aborted, so tests do
  not depend on the internet and do not send analytics events.
- **No real inbox needed.** Registration requires an emailed code; tests insert the
  verification-code row directly and then use the real `/auth/register` endpoint.
- **Isolation.** Every test creates its own user (`e2e_<tag>_<random>@example.com`) and the
  fixture deletes it afterwards; global setup and teardown remove any leftovers.

## 2. Items and features tested

| Feature | Spec / test file | Layers |
|---|---|---|
| Registration (verification code, password match, wrong code) | `auth.spec.ts` | e2e |
| Login, wrong password, logout, protected-page redirect | `auth.spec.ts` | e2e |
| Login rate limiting (429 after 10 attempts) | `auth.spec.ts` | e2e |
| Language switching on all 7 pages, logged in and logged out | `i18n.spec.ts`, `test_conversations_and_session.py`, `fetchCurrentUser.test.ts`, `no-bare-useTranslations.test.ts` | e2e, integration, unit |
| Chat: send, reply, persistence, new conversation, theme | `chat.spec.ts` | e2e |
| Cognitive game (start, answer, exit) | `chat.spec.ts` | e2e |
| Accessibility mode | `accessibility.spec.ts` | e2e |
| Voice input (mocked Web Speech API) | `voice.spec.ts` | e2e (Chromium) |
| Reminders: add, list, delete, validation, ownership | `reminders.spec.ts` | e2e (UI and API) |
| Reminder alarm on a page other than chat | `reminder-alarm.spec.ts` | e2e (Chromium, WebKit) |
| Conversation history: list, pin, rename, filter | `history.spec.ts` | e2e |
| Conversation delete: cancel, confirm, persistence, other user, logged out | `history.spec.ts`, `test_conversations_and_session.py`, `ConversationCard.test.tsx` | e2e, integration, unit |
| Profile: display name, password change | `profile.spec.ts` | e2e |
| Hong Kong guide: tabs, filtering, detail modal | `hk-guide.spec.ts` | e2e |
| Page rendering, no app errors, loading screen, no horizontal overflow | `browser-compatibility.spec.ts`, `PageLoading.test.tsx` | e2e, unit |
| Translation completeness (same keys in both languages) | `translations-parity.test.ts`, integration test | unit, integration |
| Load behaviour | `tests/stress/k6-load.js` | stress |

Not tested: see section 10.

## 3. Passing and failing criteria

- **End-to-end:** a test passes when every assertion holds. The suite passes when all tests
  pass on all four projects; a skipped test needs a stated reason (section 6). A test that
  passes only on retry is reported as flaky and counts as a defect to investigate.
- **Backend and unit suites:** every test passes.
- **Stress (k6 thresholds, evaluated by k6 itself; a breached threshold fails the run):**

  | Metric | Threshold |
  |---|---|
  | `http_req_duration` p(95), public endpoints | under 500 ms |
  | `http_req_duration` p(95), authenticated endpoints | under 1500 ms |
  | `http_req_failed`, each flow | under 1 % |
  | `checks` | above 99 % |

## 4. Test deliverables

| Deliverable | Where |
|---|---|
| Test source | `tests/e2e/`, `tests/integration/`, `tests/*.py`, `tests/unit/`, `web-next/tests/`, `tests/stress/` |
| HTML report | `playwright-report/index.html` |
| Per-test screenshots, videos, traces | `test-results/` (`npx playwright show-trace <trace.zip>`) |
| JUnit results | `test-results/junit.xml` |
| Stress summary | `test-results/stress-summary.json` |
| CI artifacts | `ci-artifacts-e2e-<project>` (one per browser project) and `ci-artifacts-stress` |

The CI workflow (`.github/workflows/ci.yml`) was extended with these jobs but has not yet
run on GitHub; CI run links will be added after the first push. The equivalent local runs
are reported below.

## 5. Black-box test

Black-box tests drive the UI or the public HTTP API only, with no knowledge of internals.
There are 64 tests per project (12 spec files). Result: see section 6.

| Spec | Tests | Scenarios |
|---|---|---|
| `smoke.spec.ts` | 2 | Backend reachable through the Next origin; login stays on the Next origin |
| `auth.spec.ts` | 9 | Register with a code; wrong code rejected; password-match indicator; login; wrong password; show/hide password; logout; redirect when logged out; 429 rate limit |
| `i18n.spec.ts` | 10 | Every page switches to zh-HK and back (5 logged in, 2 logged out); language buttons on chat and profile; localized password toggle label |
| `chat.spec.ts` | 6 | Send and reply; send button; reload persistence; new conversation; game start/answer/exit; dark theme persists |
| `accessibility.spec.ts` | 3 | Landmarks and skip link; send and reply; clear |
| `voice.spec.ts` | 2 | Mic fills the input with recognised speech; localized tooltip |
| `reminders.spec.ts` | 7 | Add and delete in the UI; form layout; localized presets; API create/list/delete; validation (400); unauthenticated (401); another user gets 404 |
| `reminder-alarm.spec.ts` | 2 | Alarm fires on `/history` with a looping sound, an alert and removal of the reminder; a reminder for another minute does not fire |
| `history.spec.ts` | 8 | List; pin and filter; rename; delete (cancel, confirm, persistence); empty state; localized confirm text; another user gets 404; logged out gets 401 |
| `profile.spec.ts` | 3 | Display name persists; wrong current password rejected; new password works for login |
| `hk-guide.spec.ts` | 4 | Five tabs and cards; category filter; detail modal and Escape; localized "Last updated" |
| `browser-compatibility.spec.ts` | 8 | See section 7 |

Supporting layers: 12 API integration tests and 7 backend unit tests (section 6), and 62
component/unit tests.

## 6. Results

| Suite | Result |
|---|---|
| Playwright, dev servers, 2 workers | 256 executions (64 x 4 projects): **246 passed, 10 skipped, 0 failed, 0 flaky** in each of the last two runs (4.8 and 5.8 min) |
| Playwright, production build (CI mode), 1 worker | Chromium 64 passed; WebKit, Pixel 5 and iPhone 13 together 182 passed, 10 skipped; 6.8 min total |
| pytest, backend unit (mocked DB) | 7 passed |
| pytest, API integration (live local PostgreSQL) | 12 passed |
| Vitest, repository root | 9 passed (2 files) |
| Vitest, `web-next` | 53 passed (7 files) |
| k6 stress, full profile | thresholds passed (section 8) |

The 10 skipped executions are intended: voice input runs on Chromium only, because the Web
Speech API is Chromium-specific (4); the alarm timing test runs on desktop projects only
(4); the reminder form layout measurement needs the desktop sidebar (2).

## 7. Browser test

Projects: Desktop Chrome (Chromium), Desktop Safari (WebKit), Pixel 5 (Chromium mobile
emulation) and iPhone 13 (WebKit mobile emulation). All 64 tests run on all four except the
skips above, so every feature in section 2 is exercised on every browser engine and both
phone form factors.

`browser-compatibility.spec.ts` adds checks specific to rendering:

- The login and register forms render their fields.
- Each of the five signed-in pages (`/`, `/history`, `/profile`, `/accessibility`,
  `/hk_guide`) renders its main landmark with no uncaught page error and no console error
  originating from the application's own origin.
- A loading screen appears while the session check is slow, then the page replaces it.
- Login and chat do not overflow horizontally on phone viewports.

Result: all pass on all four projects (included in the totals in section 6).

## 8. Stress test

**Environment.** The same FastAPI application, run locally against the local PostgreSQL
database, with the LLM key blank so chat replies use the built-in fallback (no cost and no
third-party limits). This measures the application and its database on the test machine
(section 9). It is **not** a measurement of the Vercel Hobby deployment, which the earlier
report could not load-test.

**Method.** k6 ramps two groups of virtual users (VUs): a public group (health,
translations, config) and an authenticated group (session check, conversation list,
reminders and a chat message) at half the size. Login is rate limited to 10 per minute per
IP, so the script logs in once and shares that session across VUs. Full profile:
25 VUs for 30 s, 50 for 60 s, 100 for 30 s, then ramp down (peak 150 VUs in total).

**Results (full profile).**

| Metric | Result | Threshold |
|---|---|---|
| Requests | 29,051 (about 206 per second) | |
| Failed requests | 0.00 % (public and authenticated) | under 1 % |
| Checks passed | 100 % (29,051 of 29,051) | above 99 % |
| p95 latency, public | 2.4 ms | under 500 ms |
| p95 latency, authenticated | 12.32 ms | under 1500 ms |
| Overall average / maximum | 2.61 ms / 145.38 ms | |

A 25-second smoke profile (up to 15 VUs, 866 requests) also passed; it runs in CI.

**Interpretation.** The application shows no degradation at 150 concurrent virtual users
on this machine. The thresholds sit far above the measured values, so they catch
order-of-magnitude regressions only; the run never reached the point where the system
begins to degrade, so it does not establish a capacity limit. Finding that limit would
need a breakpoint ramp, which was not done.

## 9. How to repeat

Environment used for the recorded results: Apple M2, 16 GB, macOS 26.6.2; PostgreSQL 15.17;
Node 25.6.1; Python 3.14.7; Playwright 1.59.1; k6 2.2.0. CI uses Ubuntu, Node 20, Python
3.12 and PostgreSQL 16.

```bash
brew install k6 && npm ci && npm ci --prefix web-next && npx playwright install
npm run e2e:db                       # once: create and migrate listening_tree_e2e
E2E_PYTHON=$(pwd)/.venv/bin/python npx playwright test        # all e2e
npm run test:unit && (cd web-next && npm test)                # unit tests
python -m pytest -q tests --ignore=tests/integration          # backend unit
SKIP_ENV_LOCAL=1 DATABASE_URL="postgresql://$(whoami)@127.0.0.1:5432/listening_tree_e2e?sslmode=disable" \
  SUPABASE_POOLER_URL= POSTGRES_POOLER_URL= DATABASE_POOLER_URL= RUN_LIVE_DB=1 PYTHONPATH=. \
  python -m pytest -q tests/integration                       # API integration
PYTHON=$(pwd)/.venv/bin/python npm run test:stress            # k6 (PROFILE=smoke for 25 s)
npx playwright show-report                                    # open the HTML report
```

`E2E_PYTHON` names the Python that has the backend dependencies (in CI the default
`python` is used). Setting `CI=true` makes Playwright use a production build of the front
end instead of the dev server.

## 10. Issues found, and known limitations

**Product defect found by the new suite (fixed).** On `/login` and `/register`, choosing
the Chinese language did nothing for a logged-out visitor: the session check returned no
language in its 401 response and the client discarded the body. The 401 now carries the
language, and it is pinned by an e2e test, an integration test and a unit test.

**Test-environment problems found and fixed** (none were product bugs): the dev server
refused `127.0.0.1` so pages never hydrated; the proxy reused sockets that the backend had
closed (the backend's keep-alive is now longer in tests); a hung analytics script blocked
page load (external requests are now aborted); WebKit occasionally applied a session cookie
late (the language helper now confirms and retries); parallel workers could clear each
other's rate-limit counters (the rate-limit test now has its own reserved counter).

**Limitations.**

- Chat reply quality is not tested: the LLM is disabled, so tests check that a reply
  arrives, not what it says.
- Email delivery is not tested (codes are inserted directly) and Google sign-in is not
  tested (it needs a real Google account); it was only confirmed by hand that the button
  redirects to Google.
- Browsers are Chromium and WebKit engines, and phones are emulated; there is no Firefox
  and no physical device. There is no visual (screenshot) comparison.
- Fonts and icon fonts from CDNs are blocked in tests, so rendering uses system fonts.
- Playwright is configured with one retry to absorb transport hiccups; a test that needs it
  is reported as flaky, and the recorded runs above had none.
- The stress test does not measure the Vercel deployment and did not find a capacity limit.
- The GitHub Actions jobs have not yet run (section 4).
