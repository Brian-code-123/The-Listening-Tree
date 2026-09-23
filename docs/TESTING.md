# Test Plan and Report

This document covers the test plan, strategy, criteria, deliverables and results for
The Listening Tree after the move from Jinja templates to the Next.js front end. The
functional results (sections 5 to 7) were re-recorded on 2026-09-24 (environment in section 9).
The stress results (section 8) were recorded on 2026-09-22 and have not been re-run. Where a
result is not yet available it says so.

## 1. Testing Strategy

The suite tests the system the way a user meets it: through the browser, against the same
application layout that production uses.

| Layer | Tool | What it proves |
|---|---|---|
| Black-box / end-to-end | Playwright | User flows through the real UI on 4 browser/device projects |
| API integration | pytest against a live local PostgreSQL | Endpoint contracts, ownership rules, data effects, security boundaries |
| Backend unit | pytest with a mocked database | Core flows without a database; the open-redirect guard; the reminder-command parser, the daily-reminder API and the check-in rule |
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
| Reminders: add, list, delete, validation, ownership, daily repeat | `reminders.spec.ts` | e2e (UI and API) |
| Reminder alarm on a page other than chat, and a daily reminder ringing again the next day | `reminder-alarm.spec.ts` | e2e (Chromium, WebKit) |
| Returning-user check-in (6+ hours since the user's last message in any conversation) | `checkin.spec.ts`, `test_daily_reminder_checkin.py` | e2e, backend unit |
| Daily reminders survive the nightly expiry job | `test_daily_reminders_live.py`, `reminders.spec.ts` | integration, e2e |
| Conversation history: list, pin, rename, filter | `history.spec.ts` | e2e |
| Conversation delete: cancel, confirm, persistence, other user, logged out | `history.spec.ts`, `test_conversations_and_session.py`, `ConversationCard.test.tsx` | e2e, integration, unit |
| Profile: display name, password change | `profile.spec.ts` | e2e |
| Hong Kong guide: tabs, filtering, detail modal | `hk-guide.spec.ts` | e2e |
| Page rendering, no app errors, loading screen, no horizontal overflow | `browser-compatibility.spec.ts`, `PageLoading.test.tsx` | e2e, unit |
| Translation completeness (same keys in both languages) | `translations-parity.test.ts`, integration test | unit, integration |
| Security boundaries: another user cannot read, pin, tag, rename or write into someone else's conversation; logged-out requests get no data; SQL-injection-shaped login; session cookie flags | `test_security_boundaries.py` | integration |
| Open-redirect guard on the language switch (look-alike hosts, scheme-relative and backslash paths, malformed Referer) | `test_redirect_target.py` | unit |
| Injection and odd input: HTML in a chat message, reminder label and conversation title is shown as text; whitespace-only message; Chinese and emoji text | `edge-cases.spec.ts` | e2e |
| Things changing under the user: session expiring mid-chat, a conversation deleted elsewhere then opened, deleting while renaming | `edge-cases.spec.ts` | e2e |
| Safety of the test tooling itself: refuses non-local databases and refuses to adopt a server already on its port | `e2e-env.test.ts`, `playwright.config.ts`, `run-local.sh` | unit, manual check |
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

The CI workflow (`.github/workflows/ci.yml`) runs every job on each push to `main`. Its runs
of 2026-09-23 (commits `668dcf1` and `4142a38`) failed on one test, the reminder form layout,
which the new "repeat every day" tick had broken. The fix passes locally in both modes
(section 6); the CI run link for the fix is added after that run has finished.
The equivalent local runs are reported below.

## 5. Black-box test

Black-box tests drive the UI or the public HTTP API only, with no knowledge of internals.
There are 84 tests per project (14 spec files). Result: see section 6.

| Spec | Tests | Scenarios |
|---|---|---|
| `smoke.spec.ts` | 2 | Backend reachable through the Next origin; login stays on the Next origin |
| `auth.spec.ts` | 9 | Register with a code; wrong code rejected; password-match indicator; login; wrong password; show/hide password; logout; redirect when logged out; 429 rate limit |
| `i18n.spec.ts` | 10 | Every page switches to zh-HK and back (5 logged in, 2 logged out); language buttons on chat and profile; localized password toggle label |
| `chat.spec.ts` | 6 | Send and reply; send button; reload persistence; new conversation; game start/answer/exit; dark theme persists |
| `accessibility.spec.ts` | 3 | Landmarks and skip link; send and reply; clear |
| `voice.spec.ts` | 2 | Mic fills the input with recognised speech; localized tooltip |
| `reminders.spec.ts` | 13 | Add and delete in the UI; form layout (the repeat tick has its own row and does not move the button); localized presets; a daily reminder added with the tick, marked as repeating and kept after a reload; a one-off reminder not marked; API create/list/delete; repeat=daily stored and an unknown repeat rejected (400); a daily reminder still listed three days later while a one-off one is not; the chat commands "set reminder daily ..." and "設置提醒 每日 ..."; validation (400); unauthenticated (401); another user gets 404 |
| `reminder-alarm.spec.ts` | 3 | Alarm fires on `/history` with a looping sound, an alert and removal of the reminder; a daily reminder rings, is kept, and rings again the next day in the same open tab; a reminder for another minute does not fire |
| `checkin.spec.ts` | 5 | Check-in after 7 hours away, and only once; none after 2 hours; opening an old conversation through the API writes nothing; activity in another conversation suppresses the check-in on an old pinned one; an unanswered check-in does not block the next |
| `history.spec.ts` | 8 | List; pin and filter; rename; delete (cancel, confirm, persistence); empty state; localized confirm text; another user gets 404; logged out gets 401 |
| `profile.spec.ts` | 3 | Display name persists; wrong current password rejected; new password works for login |
| `hk-guide.spec.ts` | 4 | Five tabs and cards; category filter; detail modal and Escape; localized "Last updated" |
| `edge-cases.spec.ts` | 8 | HTML in a chat message, reminder label and conversation title never executes; whitespace-only message not sent; Chinese and emoji label intact; session expiring mid-chat gives an error bubble; a deleted conversation opened by link leaves a working chat; deleting while renaming |
| `browser-compatibility.spec.ts` | 8 | See section 7 |

Supporting layers: 21 API integration tests, 25 backend unit tests, and 69 component/unit
tests (section 6).

## 6. Results

| Suite | Result |
|---|---|
| Playwright, dev servers, 2 workers | 336 executions (84 x 4 projects): **324 passed, 12 skipped, 0 failed, 0 flaky** (8.2 min) |
| Playwright, production build (CI mode), 1 worker | 336 executions: **323 passed, 12 skipped, 0 failed, 1 flaky** (10.3 min for all four projects) |
| pytest, backend unit (mocked DB) | 25 passed |
| pytest, API integration (live local PostgreSQL) | 21 passed |
| Vitest, repository root | 16 passed (2 files) |
| Vitest, `web-next` | 53 passed (7 files) |
| k6 stress, full profile | thresholds passed (section 8) |

The one flaky execution in the production-build run is `i18n.spec.ts:32` "login (logged out)
switches zh-HK <-> en" on Chromium: it hit the 45 s test timeout once and passed on the retry. It
did not reproduce in 40 consecutive runs of that test (login and register, 20 each) in the same
mode, and the dev-server run and an earlier production-build run had none. A throwaway probe of
the API path it uses (set the language, then read it back from `/me`, 200 times in a row in the
same mode) found no wrong answer and a slowest round trip of 35 ms, which rules out the API and
the proxy but not the browser navigation or machine load. The cause is not established
(section 10).

The 12 skipped executions are intended: voice input runs on Chromium only, because the Web
Speech API is Chromium-specific (4); the alarm timing tests run on desktop projects only
(6: three tests on the two phone projects); the reminder form layout measurement needs the
desktop sidebar (2).

## 7. Browser test

Projects: Desktop Chrome (Chromium), Desktop Safari (WebKit), Pixel 5 (Chromium mobile
emulation) and iPhone 13 (WebKit mobile emulation). All 84 tests run on all four except the
skips above, so every feature in section 2 is exercised on every browser engine and both
phone form factors.

`browser-compatibility.spec.ts` adds checks specific to rendering:

- The login and register forms render their fields.
- Each of the five signed-in pages (`/`, `/history`, `/profile`, `/accessibility`,
  `/hk_guide`) renders its main landmark with no uncaught page error and no console error
  originating from the application's own origin.
- A loading screen appears while the session check is slow, then the page replaces it.
- Login and chat do not overflow horizontally on phone viewports.

Result: all pass on all four projects (included in the totals in section 6; one test needed its retry in the production-build run, see section 10).

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

Environment used for the functional results recorded on 2026-09-24: Apple M2, 16 GB,
macOS 26.6.2; PostgreSQL 15.17; Node 25.6.1; Python 3.12.7 (Anaconda, the default `python`,
not the project's `.venv`); Playwright 1.59.1. The stress results (section 8) were recorded
on 2026-09-22 with the project's `.venv` (Python 3.14.7) and k6 2.2.0. CI uses Ubuntu,
Node 20, Python 3.12 and PostgreSQL 16.

```bash
brew install k6 && npm ci && npm ci --prefix web-next && npx playwright install
npm run e2e:db                       # once: create and migrate listening_tree_e2e
E2E_PYTHON=$(pwd)/.venv/bin/python npx playwright test        # all e2e
npm run test:unit && (cd web-next && npm test)                # unit tests
python -m pytest -q tests --ignore=tests/integration          # backend unit
npm run test:integration                                      # API integration (against listening_tree_e2e)
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

**Security and edge-case checks found no further product defects.** Cross-user access to a
conversation (messages, pin, tag, rename, and posting into it), logged-out access, HTML in
user text, SQL-injection-shaped logins, session cookie flags and the open-redirect guard all
behaved correctly, so these tests are regression pins rather than fixes.

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
  is reported as flaky. The dev-server run above had none; the production-build run had one
  (`i18n.spec.ts:32`, a single 45 s timeout that passed on retry and did not reproduce in 40
  repeats or in a 200-round-trip probe of its API calls), and its cause is not established. An earlier run on 2026-09-24 that overlapped with
  other test commands on the same machine had 2 flaky tests at its very start (an `ENOENT` on the
  `test-results` artifacts folder, then a timeout); runs with nothing else running had at most
  the one above. Run one suite at a time.
- The stress test does not measure the Vercel deployment and did not find a capacity limit.
- The first GitHub Actions runs (2026-09-23) failed on the reminder form layout test (section 4). The `Secure` cookie flag only applies
  in production and is not asserted locally.
- The test tooling never adopts a server that is already listening on its ports (a stale
  one could be using another database), so a leftover process on port 3100 or 5100 makes a
  run fail immediately; stop it and re-run.
- The check-in can be inserted twice if the chat page is opened in two tabs at the same
  moment (there is no lock). Stored chat timestamps are naive server-local time, so rows
  written from a machine in another time zone can cause one early or late check-in.
- Daily reminders use the native scheduler's daily repeat (`every: "day"`); no automated
  test exercises it and it has not been checked on a physical device. Messages about
  self-harm get no special handling (see the README, "Known gaps").
