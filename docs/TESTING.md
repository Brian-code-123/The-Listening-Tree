# Test Plan and Report

This document covers the test plan, strategy, criteria, deliverables and results for
The Listening Tree after the move from Jinja templates to the Next.js front end. The
functional results (sections 5 to 7) were re-recorded on 2026-09-24 (environment in section 9).
The stress results (section 8) were recorded on 2026-09-22 and have not been re-run. Where a
result is not yet available it says so.

## Latest results (22 to 23 Oct 2026, final code)

Run on a developer laptop against a local PostgreSQL, so these are local numbers; none was measured on the Vercel deployment. How to repeat each one, the criteria and the history are in the sections below.

**Correctness**

| Suite | Result |
|---|---|
| Backend unit tests (mocked database) | 93 passed |
| API integration tests (local PostgreSQL) | 108 passed |
| Component and hook tests, `web-next` (Vitest) | 112 passed; `tsc` clean; lint 0 errors |
| Unit tests, repository root (Vitest) | 16 passed |
| End to end (Playwright: Chromium, WebKit, Pixel 5, iPhone 13) | 352 passed, 12 skipped by design, 0 failed |
| Dependency audit (`npm audit --omit=dev`, `pip-audit`) | 0 findings in shipped code (dev tooling still lists advisories, see Known gaps) |

**Performance and load**

| Test | Result |
|---|---|
| Single user, 15 virtual users for 25 s (k6 smoke) | signed-in p95 9.4 ms, public p95 2.5 ms, 0 % errors. The hardening changed this by under 1 ms (before: 7.4 ms and 3.0 ms). |
| 50 users chatting with a slow mock model, plus a burst of 30 sign-ins (k6, two runs) | 0 errors; sign-in burst done in 14 s; `/me` p95 86 to 200 ms during the burst; whole 3.5 s mock reply p95 4.5 to 4.7 s |
| 10 users, 30 messages to the real free model (`glm-4-flash`) | all 30 answered; first words median 0.85 s (max 2.2 s); whole reply median 3.3 s (p90 5.5 s) |
| Chat as the user sees it | first words after about 1 s (was a 2.6 s wait for the whole reply); the model itself writes about 20 tokens a second, so the whole reply takes 2 to 4 s |
| Password hashing | 207 ms per sign-in (was 141 ms at 390k rounds), in a worker thread so other requests are not delayed |

**What the testing found and fixed** (each has a regression test): the connection pool deadlocked when 10 or more sign-ins arrived together (found by the many-user test, not the single-user one); a browser leaving mid-reply lost the reply and leaked a connection; the speech fallback froze the whole server for about a second; a failed model call leaked a database connection and later hung the pool; one rate-limit test was flaky because of a fixed-window boundary.

**Not measured:** performance on the Vercel deployment (session-check cost, real password-hash time, whether the stream is delivered unbuffered, function concurrency), Zhipu's concurrency limit above about 10 simultaneous users, Core Web Vitals after the changes, and server-side speech-to-text with real speech (the Hugging Face account had no credit when checked).

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
| Security hardening: schema; atomic per-email+IP lockout and timing; password policy and rehash; verification-code limits and enumeration; security events and log hygiene; session revocation; Google linking; message/body/reminder/public-data limits; crisis and scam pre-check; cron retention; account delete and export | `test_security_schema.py`, `test_security_login.py`, `test_security_passwords.py`, `test_security_codes.py`, `test_security_events.py`, `test_security_session.py`, `test_security_google.py`, `test_security_limits.py`, `test_security_safety.py`, `test_cron_cleanup.py`, `test_account.py` | integration |
| Security hardening (no database): trusted client IP, password policy, security headers (and parity with `next.config.ts`), safety keyword rules, prompt hygiene | `test_rate_limit_ip.py`, `test_password_policy.py`, `test_security_headers.py`, `test_safety.py`, `test_prompt_hygiene.py` | backend unit |
| Sessions end on the server; rate limits per address; privacy notice and consent tick | `tests/e2e/security.spec.ts` | e2e |
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
(section 6) and in CI: [run 35902287611](https://github.com/Brian-code-123/The-Listening-Tree/actions/runs/35902287611)
(commit `3227d44`, all 10 jobs succeeded).
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

Supporting layers: 24 API integration tests, 33 backend unit tests, and 111 component/unit
tests (section 6).

## 6. Results

| Suite | Result |
|---|---|
| Playwright, dev servers, 2 workers | 336 executions (84 x 4 projects): **324 passed, 12 skipped, 0 failed, 0 flaky** (8.2 min) |
| Playwright, production build (CI mode), 1 worker | 336 executions: **323 passed, 12 skipped, 0 failed, 1 flaky** (10.3 min for all four projects) |
| pytest, backend unit (mocked DB) | 33 passed |
| pytest, API integration (live local PostgreSQL) | 24 passed |
| Vitest, repository root | 16 passed (2 files) |
| Vitest, `web-next` | 95 passed (9 files) |
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

## Non-functional requirements after the security hardening (22 Oct 2026)

Measured on a local machine (Apple silicon, local PostgreSQL, k6 smoke profile: 15 virtual users, 25 s), the same script against the commit before the hardening and after it. **These are local numbers; nothing here was measured on the Vercel deployment.**

| Requirement | Target | Before | After | Verdict |
|---|---|---|---|---|
| Signed-in request latency (p95) | < 1500 ms | 7.4 ms | 8.3 ms | Met. The per-request session check (one indexed lookup) costs about 0.5 ms locally. |
| Public request latency (p95) | < 500 ms | 3.0 ms | 3.8 ms | Met. |
| Error rate | < 1 % | 0 % | 0 % | Met. Chat answers 429 once a user passes 20 messages a minute; the load test accepts 200 or 429 and fails on any 5xx. |
| Password hash cost (one sign-in) | no event-loop stall | 141 ms (390k) | 207 ms (600k) | +66 ms per sign-in. Hashing runs in a worker thread; a test checks other requests are not delayed while hashing. Serverless CPUs are slower than this laptop, so expect more on Vercel; not measured. |
| Cold start (`import run`) | no regression | 0.72–0.86 s | 0.73–1.15 s | No measurable change (noisy). |
| Extra database round trips | few | — | session check +1 on every signed-in request; chat +2 (two limiter upserts); sign-in +2 to +3 | Cheap in the same region (function and database are both in Tokyo) but **not measured on Vercel**. |
| Behaviour when the database is down | no stack traces | — | limiter: 503 with a clean body; session check: request allowed and logged | Covered by tests. |
| Request body size | bounded | unbounded | 1 MB (11 MB for voice), checked before parsing | Covered by tests. |
| Page weight / Core Web Vitals | no regression | — | privacy page and consent checkbox added; no new third-party scripts | Not re-measured. |

Not measured and worth doing after deploy: the session check's cost on Vercel (look at p95 of `/me` in the runtime logs), real PBKDF2 time on a Vercel function, and whether the CSP report-only policy raises violations in a real browser.

### Chat and speech-to-text response time (22 Oct 2026, real external calls)

Timed from a laptop in Hong Kong against the live providers with the project's own keys, so the figure includes the network to the provider. These calls are the slowest thing in the app and the app cannot make them faster; the table says what the user waits for.

| Path | Result | Notes |
|---|---|---|
| Chat reply, English (Zhipu `glm-4-flash`, 8 calls) | min 3.1 s, median 4.1 s, p90 about 5.1 s, max 10.9 s | Reply of about 360 characters. The app's own overhead (limiter, session check, two writes) is a few milliseconds and is lost in this. |
| Chat reply, Cantonese (8 calls) | min 2.4 s, median 3.5 s, p90 about 3.8 s, max 5.4 s | Replies are shorter. |
| Chat, model unreachable | up to the 60 s client timeout, then a warm fixed fallback reply | The user waits the full timeout before the fallback appears; a shorter timeout is a product decision. |
| Speech-to-text, Whisper via Hugging Face | **fails: HTTP 402, "no remaining credits"** (0.5 s to fail) | The key in `.env.local` has no credit. If production uses the same account, server transcription never uses Whisper. |
| Speech-to-text, Google fallback | not measured with real speech | This machine's speech synthesiser does not work in the sandbox, so no real speech clip could be made, and the clip used got "Bad Request" from Google. The failed Whisper try plus the fallback together took about 1 s. |

Findings from this check:

1. **The Hugging Face account is out of credit.** Most browsers use the built-in Web Speech API instead and never reach `/transcribe`, so users may not notice. Top up the account or remove `HF_API_KEY` to skip the wasted 0.5 s round trip.
2. **Fixed:** the Google fallback was a blocking call made inside an async route, so each use froze every other request on that instance for about a second. It now runs in a worker thread (test: `test_google_fallback_does_not_block_the_event_loop`).
3. **Fixed:** `get_response` could leak a database connection when anything inside it raised, which later hung the pool. It now releases the connection in a `finally` and `close()` is idempotent (test: `test_a_failing_model_call_does_not_leak_a_database_connection`).
4. **Chat now streams** (below).

#### Why chat was slow, and what changed

Root cause, measured: the wait is the model writing, not connections or our code. `glm-4-flash` decodes about 20 tokens a second (a 64-token reply is about 3 s), reusing the HTTP connection made no difference, and our own overhead is a few milliseconds. The faster Zhipu models (`glm-4-flashx`, `glm-4-air`) answer "insufficient balance" on this account, so a faster model needs a paid top-up.

What the app can change is what the user *sees*: the model's first words arrive after about 0.8 s, so the reply is now sent as server-sent events and shown as it is written, with an empty "…" bubble up at once.

Measured through the real server and live model (6 streamed messages, 3 plain, English and Cantonese):

| | min | median | max |
|---|---|---|---|
| Before: wait until the reply appears | 2.1 s | 2.6 s | 3.7 s |
| After: first words appear | 1.0 s | **1.0 s** | 1.9 s |
| After: whole reply complete | 2.0 s | 2.6 s | 3.8 s |

The whole reply takes the same time; the user stops staring at a blank screen after one second. Industry practice for chat is time-to-first-token under about a second, which this meets. Speech now starts with the first finished sentence (`nextSentences` in `lib/tts.ts`; later sentences queue behind it instead of cutting it off). Not done: the first-word figure includes about 0.2 s of our own database work that could be trimmed.

Not verified: that the Vercel Python runtime delivers the stream unbuffered. It is covered locally by integration tests (`test_chat_streaming.py`) and the client falls back to a plain JSON reply if the server does not stream, so the worst case is the old behaviour; check the first-words time on the deployed site after release.

### Final run, 22 Oct 2026

| Suite | Result |
|---|---|
| Backend unit (mocked database) | 93 passed |
| API integration (local PostgreSQL) | 105 passed |
| Vitest, `web-next` | 112 passed; lint 0 errors; `tsc` clean |
| Vitest, repository root | 16 passed |
| Playwright, all four projects (Chromium, WebKit, Pixel 5, iPhone 13) | 351 passed, 12 skipped, 1 flaky |
| k6 smoke | all thresholds met |

The one flaky test was the per-IP login limit on WebKit: the limit is a fixed one-minute window, so twelve requests that straddled a minute boundary were counted in two windows and never reached 10. The test now starts early in a window (6 repeated runs with no retries all passed). The same boundary effect exists for real users, who can send up to twice the limit across a boundary; that is the documented cost of a fixed window.

### Many users at once, with a slow model (22 Oct 2026)

`npm run test:stress:multiuser` starts a mock Zhipu server (`tests/stress/mock_zhipu.py`: half a second to the first words, about 3.5 s for a whole reply), 50 different signed-in users each chatting every 3 seconds with streaming, a burst of 30 sign-ins in the middle of the run, and two watchers polling `/me`. It uses the local e2e database and never the real model or any quota.

**It found a real defect that the single-user test could not.** The first run hung: all 60 sign-ins timed out after 60 s, 25 % of chat requests stalled, and `/me` waited up to a minute, with no server errors at all. Cause: the database pool holds at most 10 connections, and the sign-in handler kept one connection while asking for a second (`reset_key` and `record_event` each borrow their own). With 10 sign-ins in flight every connection was held by a request waiting for another, so the pool deadlocked. Registration and the chat safety event had the same shape, and the chat reminder commands already did.

Fixes: the sign-in, registration and chat handlers now give a connection back before borrowing another (and before hashing a password), the pool size is configurable with `DB_POOL_MAX`, and `tests/integration/test_pool_deadlock.py` runs four times more simultaneous sign-ins, chats (including safety messages and reminder commands) and registrations than a 3-connection pool has connections. That test hung for 40 s before the fix and finishes in a few seconds after it.

| After the fix (two runs) | Result |
|---|---|
| Sign-in burst of 30 (60 sign-ins) | all 200; the burst finishes in 14 s instead of timing out |
| `/me` while the burst runs | p95 86 to 200 ms (max about 0.8 s) |
| Whole chat reply with the 3.5 s mock model | p95 4.5 to 4.7 s, no stalls |
| Server errors, connection resets | 0 |

Two test-design lessons are recorded in the script: k6 buffers a streamed body, so it measures the whole reply and not the first words (those were timed separately above); and the sign-in burst sleeps 8 s, not 5, because uvicorn closes an idle connection after 5 s and a client that reuses it at that instant sees a reset.

Still not tested: the real Zhipu concurrency limit (needs your quota and approval), the Vercel runtime (function concurrency, cold starts under load), and the full 100-user profile of the single-user test.

### Small real-model check (23 Oct 2026)

`npm run test:stress:realai`: 10 different users, 3 messages each about 10 seconds apart, streamed, to the live free `glm-4-flash` through a local backend and the local e2e database (about 30 model calls, no production data, key read from `.env.local` and never printed).

| | Result |
|---|---|
| Requests | 30, all answered 200 with a real model reply (0 fallbacks, 0 rate-limit answers from Zhipu) |
| First words | min 0.71 s, median 0.85 s, p90 1.65 s, max 2.19 s |
| Whole reply | min 1.40 s, median 3.33 s, p90 5.46 s, max 7.25 s |

At this size (about 10 users at once) Zhipu's free tier did not push back. Its concurrency limit at higher load is still unknown, and so is how the Vercel runtime behaves with many streams open.

