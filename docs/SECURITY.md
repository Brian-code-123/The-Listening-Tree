# Security and Privacy Design

What the code does today, why each choice was made, what it costs and what it cannot do. Last checked against the code on 22 Oct 2026. Numbers that change with every commit (test counts, timings) are not repeated here; see [TESTING.md](TESTING.md). Steps the owner must take before the features are live are in [DEPLOYMENT.md](DEPLOYMENT.md#before-this-goes-live).

## Security design (implemented)

**Passwords and sign-in**
- Passwords are PBKDF2-HMAC-SHA256 with a unique salt and 600,000 iterations (the current OWASP figure), compared in constant time. A hash made with fewer iterations is upgraded on the next successful sign-in. Hashing runs in a worker thread so a burst of sign-ins does not stall other requests. Length is 8 to 128 characters; longer input is refused before any hashing, so it cannot be used to burn CPU.
- A failed sign-in always returns the same message and status, and an unknown email still costs one hash (against a dummy hash), so neither the text nor the response time says whether an account exists.
- Lockout counts failures per email **and** IP: 5 failures in 15 minutes lock that pair, and the lock ends by itself when the window ends. A second, higher ceiling per email (30 in 15 minutes) bounds guessing spread over many IPs. A successful sign-in clears the pair. The counter is one atomic SQL statement, so ten parallel guesses cannot all slip under the limit.
- Changing a password needs the current one, is limited to 5 attempts per 10 minutes, and signs out every other device.
- Google Sign-In verifies the ID token with Authlib and requires a verified Google email. A blocked (`is_active = false`) account is refused.
- Registration needs a 6-digit emailed code. Codes come from `secrets.randbelow`, are stored only as an HMAC of the email and code (a copy of the table cannot be replayed), expire in 5 minutes, work once, and a new code retires the older ones. Guessing is limited to 5 wrong codes per email per 10 minutes, a new code per address once a minute and 10 a day. Asking for a code for an already-registered email gets the same neutral answer as a new one, and nothing is sent, so the form does not reveal who has an account.
- Registration needs an explicit tick for the privacy notice; the time and notice version are stored with the account.

**Sessions**
- The session is a signed cookie (`lt_session`): `SameSite=Lax`, `HttpOnly`, `Secure` in production. "Remember me" keeps it 90 days; without it the server also enforces a 12-hour expiry, not just the browser dropping it.
- Every signed-in request is checked against the database for the user's `session_version` and `is_active`. Logging out (now `POST`, so a foreign page cannot trigger it) and changing the password raise the version, so every copy of the old cookie stops working at its next request. A deleted or blocked user's cookie stops working too. Cookies issued before this change carry no version and count as version 0, so nobody was signed out when it shipped.
- Signing in starts a fresh session (only the language choice is carried over), so an old session id is never promoted.
- The signing key comes from `SECRET_KEY` / `SESSION_SECRET`. In production the app refuses to start without one.

**Abuse prevention**
- Counters live in PostgreSQL (`rate_limit_events`), so limits hold across serverless instances: per IP, 10 sign-ins, 5 registrations, 5 code requests, 20 voice uploads and 120 public-data reads per minute; per signed-in user, 20 chat messages a minute and 300 a day (every non-command message is a paid model call), 5 password changes or account deletions per 10 minutes.
- The client IP comes from `X-Forwarded-For` only where a trusted proxy sets it (`VERCEL`, or `TRUSTED_PROXY=1`). Elsewhere the header is ignored, so a caller cannot invent addresses. Values that are not valid IPs are discarded and IPv6 is bucketed by /64.
- If the limiter's database is unreachable the request is refused with 503 (it fails closed); a clean message, not a stack trace.
- Input bounds: chat message 2,000 characters; request bodies 1 MB (11 MB for the voice upload), checked by declared length and, for chunked bodies, by counting bytes as they arrive, before any parser buffers them; at most 50 active reminders and a 100-character label; display name 50; ids in URLs must be in range; `set preference` accepts only a known key and value; conversation and message caps per user as before.
- `?refresh=1` on the public guide is ignored unless signed in, so a visitor cannot force recomputation.

**Security events and logs**
- `security_events` records sign-in success and failure, lockouts, registration, code sends and failures, password changes, logout and revoked sessions, Google sign-in and linking, rate-limit hits, safety triggers, account deletion and data export. Each row has the time, event, user id, a keyed hash of the email (never the address), the IP and a truncated user agent. Passwords, codes, tokens and message text are never logged, and the same event goes to the platform log as one JSON line (control characters in an email cannot forge a second line). A failure to write an event never fails the request. Rows are deleted after 180 days.
- Personal data was removed from other logs: device tokens, reminder labels and email addresses no longer appear.

**Response and exposure**
- Headers on every response: `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options: DENY`, `Permissions-Policy` (microphone only for this site) and a Content-Security-Policy. The same list is set by the Next.js app, and a test fails if the two copies drift apart.
- In production `/docs`, `/redoc` and `/openapi.json` are off, the health endpoint returns only `{ok}`, CORS is an explicit list without localhost, and unexpected errors return a generic body with a request id instead of a stack trace.

**Data access, injection and the browser**
- Every query on user data is parameterized and scoped by `user_id`. Another user's conversation or reminder answers 404. Tests cover read, pin, tag, rename, delete and write across two users.
- Chat text, news items and names are written into the page as text, never as HTML, in the Next.js app and the two legacy pages. The display name is flattened again (no newlines, 30 characters) before it goes into the model prompt.
- Row Level Security is on for every public table, with no policies (REST access is denied). The app's own role bypasses RLS, so RLS is a second line, not the access control.
- A local run cannot connect to the deployed database unless `ALLOW_PRODUCTION_DB=1`, and the e2e suite uses its own database. Schema changes are Alembic migrations; the security migration only adds (columns, a table, one unique index on `LOWER(email)`), so old and new code both run against it.

**Privacy**
- `/privacy` (English and Cantonese) says what is kept, why, who else processes it, for how long, and how to take it back.
- **Delete my account** (Profile) erases chats, conversations, reminders, preferences and the user row in one transaction, after the password (or, for a Google account, a sign-in in the last 5 minutes). **Download my data** returns the user's profile, conversations, messages, reminders and preferences as a JSON file, never the password hash and never another user's rows.
- A daily Vercel cron (`/internal/cron/cleanup`, bearer `CRON_SECRET`, refuses everyone if the secret is not set) runs the retention jobs that the background loop never ran on Vercel: soft-deleted conversations and messages are erased after 30 days, used or day-old-expired verification codes, old rate-limit rows and 180-day-old security events are deleted, old one-off reminders expire.

**AI safety**
- Before the model is called, the message is checked by plain keyword rules in English and Cantonese. Self-harm or a medical emergency gets a fixed, reviewed reply with 999 and the Samaritans line (2896 0000), and the model is never asked. Scam talk (transfers, prizes, someone claiming to be police or a bank) still goes to the model with an added warning and the Anti-Deception line (18222). Everyday idioms such as 笑死我 or "to die for" are excluded. Only the category is logged, never the words.
- The system prompt now forbids diagnosis and doses, points to 999 in an emergency, and forbids asking for passwords or codes.

**Supply chain and deployment**
- `next` is 16.4.2; `npm audit --omit=dev` reports 0 in both `web-next` and the root, and `pip-audit` reports none for `api/requirements.txt` (Authlib, python-multipart and python-dotenv were upgraded). CI now has a secret scan (gitleaks), the Node and Python audits, read-only workflow permissions and 3-day artifact retention; Dependabot is on for npm, pip and Actions. The pre-push script fails if gitleaks is missing instead of warning.
- The Capacitor config is release-grade by default (no cleartext, no mixed content, no WebView debugging); `CAP_ENV=development` turns the loose settings back on. The Docker image runs as a non-root user and installs from the trimmed manifest. Tests, docs and migrations are excluded from the Vercel upload.

## Where user data goes

- Chat: each message and up to the last 20 of that conversation are sent to Zhipu AI (`open.bigmodel.cn`, China-based) to write the reply. We do not control its retention or training use.
- Voice: browsers with the Web Speech API send audio to their vendor's recogniser ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API/Using_the_Web_Speech_API)); others upload to `/transcribe`, which uses Hugging Face Whisper or Google Web Speech. Whisper needs a funded Hugging Face account; see item 5 under [Before this goes live](DEPLOYMENT.md#before-this-goes-live).
- Email: verification codes go through Azure Communication Services. Hosting is Vercel and Supabase; page analytics use Vercel Web Analytics.
- The registration tick records agreement to a notice that lists these transfers. It is one agreement to the whole notice, not a separate choice per processor.

## Design decisions and trade-offs

Each entry says what was chosen, what it costs and what it cannot do.

**Sessions: signed cookie plus a version number in the database**
- Chosen because Vercel has no long-lived process, and a session table or Redis is new infrastructure. Revocation costs one indexed query per signed-in request (function and database are both in Tokyo).
- If that query fails, the request is let through and the failure is logged: during a database outage availability for elderly users wins over strict revocation. The rate limiter makes the opposite choice (refuse) because failing open there would remove the brute-force protection.
- Cannot do: sign out one device out of several. The version is per user, so "log out" and "change password" end every device.

**Passwords: PBKDF2 from the standard library, not argon2**
- Avoids native wheels on Vercel (smaller bundle, faster cold start, fewer packages). Cost: not memory-hard, so offline cracking on GPUs is cheaper than against argon2. Each hash records its scheme and iterations, so moving later is a re-hash on login.

**Rate limiting in PostgreSQL**
- Works across serverless instances without another service. Cost: an extra write per limited request; a fixed window allows up to twice the limit across a boundary; a database outage makes sign-in unavailable (deliberate, see above). Cannot stop a distributed attacker who rotates IPs: the per-email ceiling is the second layer.

**Lockout per email and IP**
- An attacker on another IP cannot lock the real user out, and a lock expires by itself. Cost: guessing slowly from many IPs is bounded only by the per-email ceiling of 30 in 15 minutes, and reaching that ceiling still locks everyone out of that email for the rest of the window.

**No CAPTCHA and no multi-factor sign-in (deliberate)**
- The users are elderly; CAPTCHAs and code apps add load and fail accessibility checks, and an unusable sign-in is a safety risk of its own. Account takeover is stopped only by the password, the limits and the lockout. A reused, leaked password is not protected.

**Not revealing whether an email is registered**
- Code requests answer the same either way. Cost: someone who forgot they have an account gets no hint (the sign-in page offers the way back). Cannot hide it entirely: registering with a valid code still reports a duplicate, but that needs the mailbox.

**Linking Google to an existing password account keeps the password**
- The first plan was to invalidate the old password at link time, against "pre-hijacking" (an attacker registers a victim's email first, the victim later signs in with Google, the attacker keeps the password). That attack needs a code mailed to the victim's address to register, so the attacker cannot create the account. Invalidating the password would lock out people who have one. Cost: if a mailbox is ever controlled by someone else, they can register first. Linking still requires a verified Google email; revisit if registration stops requiring the code.

**Content-Security-Policy allows inline scripts, and starts in report-only mode**
- Pages are prerendered, so there is no per-request response to carry a nonce; a nonce policy would end CDN caching. The policy blocks third-party scripts, `eval`, framing and foreign form targets but not an injected inline script. The real defence is that the live frontend has no HTML-injection sinks. It is sent as `Content-Security-Policy-Report-Only` until `CSP_ENFORCE=1` is set, so a mistake cannot blank the site; reports are only visible in browser consoles because there is no report collector.

**Audit log in the same database**
- Easy to query, but someone with write access to the database can alter it, nothing alerts on it, and the 180-day retention is a privacy choice, not a compliance period. Cannot do tamper-evidence or alerting without an external log service.

**Deletion is real but bounded**
- Account deletion erases rows in one transaction. It cannot erase Supabase backups or recall text already sent to Zhipu AI, Hugging Face or Google; the privacy page says so. Ordinary deleted conversations stay 30 days (soft delete) before the cron erases them, and the cron runs once a day, so "30 days" means 30 to 31.

**Chat content is plain text in the database**
- The server needs it to rebuild context and show history. Field-level encryption adds key management and breaks server-side features, so protection is per-user scoping, RLS and Supabase encryption at rest. A database leak would expose conversations that can hold health and family details.

**Crisis detection is keywords, not a classifier**
- A fixed reply with real help lines, without calling the model, beats a cheerful or unsafe model answer. Cost: indirect wording is missed and harmless text occasionally fires. It is not a clinical tool and cannot alert a carer: there is no carer contact or consent model, which is a product decision.

**Database role**
- The app role bypasses RLS and is not least-privilege, so an injection bug would have full table access. Mitigation is parameterized queries only; a restricted role is not done because migrations and the app share one connection setup.

## Known gaps and limits

- **No external review.** Single maintainer: no penetration test, no formal threat model, no bug bounty, no incident process beyond this repository.
- **The privacy notice is not legal advice.** It was drafted from what the code does and needs the owner's review (and a contact address, set with `NEXT_PUBLIC_PRIVACY_CONTACT`) before it is relied on. Consent is one tick for the whole notice.
- **Safety keywords need clinical and local review.** The word lists were written for this project and tested against idioms, not by a counsellor.
- **Sessions are per user, not per device** (see above), and the session check fails open if the database is down.
- **Dev tooling advisories.** `npm audit` including dev dependencies still lists 49 findings in build tooling (the Vercel and Capacitor CLIs and asset generators). None ships to users or runs on the server. `pip-audit` only covers the Vercel manifest, and Python packages are pinned without hashes.
- **GitHub Actions are pinned to major tags, not commit SHAs**, so a compromised tag would be picked up.
- **Connection pool of 10.** Handlers must never hold a database connection while borrowing another, or the pool deadlocks under load (found and fixed on 22 Oct 2026; `test_pool_deadlock.py` guards sign-in, registration and chat). New code that calls `record_event`, `reset_key` or the reminder service must do so after releasing its own connection. The pool size is `DB_POOL_MAX` (default 10); Supabase's pooler caps total connections, so raise it with care.
- **Slow external answers.** The model writes about 20 tokens a second, so a whole reply takes 2 to 4 seconds. The reply is streamed, so the first words show after about 1 second (measured in [docs/TESTING.md](TESTING.md)); a faster model needs a paid Zhipu top-up. Streaming on Vercel was not verified. Spoken replies start with the first finished sentence. The Hugging Face key used for server transcription had no credit when checked, so that path falls back to Google.
- **Encryption at rest relies on Supabase** and is not independently verified. The shared Supabase project also holds unrelated tables (`document_chunks`, `page_snapshots`, `query_log`) and a `vector` extension in `public`, left alone on purpose.
- **Not measured on the deployment:** the per-request cost of the session check on Vercel (locally it is a single indexed lookup), and whether the CSP report-only policy produces violations on real pages.
