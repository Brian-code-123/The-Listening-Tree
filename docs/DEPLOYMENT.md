# Deployment

- Web: hosted on Vercel at https://the-listening-tree.vercel.app/
- Mobile: native iOS and Android apps built via Capacitor for App Store and Google Play readiness.
- Database: managed PostgreSQL on Supabase for secure and scalable storage.

## Environment variables the security and chat features read

| Variable | Needed for | If missing |
|---|---|---|
| `SECRET_KEY` (or `SESSION_SECRET`) | Signing the session cookie; hashing verification codes and email addresses in the security log. Use at least 32 random bytes. | Production refuses to start. |
| `CRON_SECRET` | Authorises the daily retention job (`/internal/cron/cleanup`). | The job refuses everyone; nothing is cleaned up. |
| `CSP_ENFORCE` | `1` turns the Content-Security-Policy from report-only into enforcing. Set in production on 23 Oct 2026. | Report-only. |
| `TRUSTED_PROXY` | `1` when the app sits behind a proxy you control, so `X-Forwarded-For` is trusted. Vercel is detected automatically. | The header is ignored; the socket address is used. |
| `NEXT_PUBLIC_PRIVACY_CONTACT` | A contact address shown on `/privacy` (baked in at build time, so redeploy after changing it). | No address is shown. |
| `DB_POOL_MAX` | Size of the database connection pool (default 10). | 10. |
| `ZHIPU_API_KEY`, `ZHIPU_MODEL`, `ZHIPU_BASE_URL` | The chat model. | Warm fixed replies instead of the model. |
| `HF_API_KEY`, `HF_WHISPER_MODEL` | Server-side speech-to-text (Whisper). Needs a funded Hugging Face account. | Falls back to Google Web Speech. |
| `ALLOW_PRODUCTION_DB` | `1` lets a local run connect to the deployed database. Leave unset except for a deliberate migration. | A local run refuses to connect. |

## Before this goes live

These need the owner; the code works without them but the matching feature is off or open until they are done.

1. ~~Run the migration on the production database~~ **Done 22 Oct 2026** (applied through the Supabase MCP because `.env.local` points at a local database; `alembic_version` is now `a3c91e7d2b54`; existing sessions stay valid).
2. ~~Set `CRON_SECRET` in Vercel~~ **Done 22 Oct 2026** (sensitive, production). It takes effect on the next deploy.
3. ~~Set `CSP_ENFORCE=1`~~ **Done 23 Oct 2026.** The public pages (login, register, privacy, guide) load with no blocked resources under the enforcing policy, and the front end loads nothing from other origins. The signed-in pages (chat, profile) were not checked in a browser under enforcement; if one looks broken, remove the variable and redeploy to go back to report-only.
4. `NEXT_PUBLIC_PRIVACY_CONTACT` is deliberately **not set** yet (the privacy page then shows no contact address; set it to a dedicated address before relying on the page, then redeploy). Review the privacy page text and the crisis wording, and confirm `SECRET_KEY` is at least 32 random bytes.
5. The Hugging Face account behind `HF_API_KEY` has no credit: on 23 Oct 2026 the **production** key answered HTTP 402, so server-side Whisper never works and every `/transcribe` call falls back to Google Web Speech after a wasted 0.5 s. Most browsers use the built-in Web Speech API and never reach this path. Either add credit (Whisper large-v3 is usually more accurate for Cantonese than the free fallback) or remove `HF_API_KEY` from Vercel so the app goes straight to the fallback.
6. Revoke the old Kimi/Moonshot key at the provider's console (only the owner can; no variable for it exists in Vercel production, so the app does not use it). The unrelated Supabase tables and the `vector` extension are gone as of 23 Oct 2026.
