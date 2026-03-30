# The Listening Tree DevOps Runbook

This runbook defines a full CI/CD flow for local development, Vercel deployment, and Capacitor mobile delivery.

## 1. What is now automated

- CI on push/PR with Python test suite and Capacitor Android sync checks.
- CD on push to `main` with Vercel build and production deploy.
- Post-deploy production smoke test against health/auth/core endpoints using `scripts/vercel_e2e_check.py`.
- Manual iOS sync workflow on macOS runner for full mobile parity.

Workflows:
- `.github/workflows/ci.yml`
- `.github/workflows/deploy-vercel.yml`
- `.github/workflows/mobile-ios-check.yml`

## 2. Required GitHub repository secrets

Set these in GitHub repository settings -> Secrets and variables -> Actions.

Required for deployment:
- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

Optional but recommended:
- `VERCEL_PRODUCTION_URL` (example: `https://the-listening-tree.vercel.app`)

## 3. Required Vercel environment variables

Set these in Vercel project settings -> Environment Variables (Production and Preview).

- `DATABASE_URL`
- `SECRET_KEY`
- `ZHIPU_API_KEY`
- `ZHIPU_BASE_URL` (optional, has default)
- `ZHIPU_MODEL` (optional, has default)
- `NEWS_API_KEY` (optional)

Important database note:
- Use a connection string reachable from Vercel runtime.
- If direct DB host fails in production, use your Supabase transaction pooler connection string.
- Keep SSL enabled in production DB URL.

## 4. Local development checklist

1. Install Python dependencies:
   - `pip install -r requirements.txt`
2. Install Node dependencies:
   - `npm install`
3. Configure `.env` with required keys.
4. Run backend:
   - `python run.py`
5. Run local quality checks:
   - `npm run ci:python`
   - `npm run ci:mobile`
   - `npm run ci:mobile:ios` (requires healthy local Xcode + CocoaPods)

## 5. Vercel deployment flow

1. Push to `main`.
2. GitHub Action `Deploy to Vercel` runs:
   - pull env from Vercel
   - Vercel build
   - production deploy
3. `Verify Production Health` runs `scripts/vercel_e2e_check.py`.
4. Deployment is accepted only when smoke test passes.

## 6. Mobile delivery flow (Capacitor)

iOS:
1. `npm run mobile:ios`
2. In Xcode, archive and distribute.

Android:
1. `npm run mobile:android`
2. In Android Studio, generate signed bundle/APK.

Before store submission:
- Confirm backend production URL and API behavior.
- Verify login/session/reminder/game flows on real device.
- Run accessibility checks (font size, touch target, color contrast).

## 7. Production verification commands

Use these checks after deployment:

- `python3 scripts/vercel_e2e_check.py`
- `curl -i https://the-listening-tree.vercel.app/health`
- `curl -i https://the-listening-tree.vercel.app/health/db`

## 8. Incident playbook

If register/login fail in production:
1. Check `/health/db` first.
2. If `/health/db` is 500, fix `DATABASE_URL` and redeploy.
3. Validate `SECRET_KEY` exists and is stable.
4. Re-run `scripts/vercel_e2e_check.py`.

If local Supabase DB cannot start:
0. Use automated recovery script:
   - `bash scripts/supabase_db_recover.sh`
1. Confirm Docker daemon is running:
   - `docker info`
2. If daemon is not running, start Docker Desktop and retry.
3. Start DB-only service first to isolate database issues:
   - `supabase db start --debug`
4. Verify Postgres container is healthy:
   - `docker ps --format 'table {{.Names}}\t{{.Status}}' | grep supabase_db_`
5. Verify DB query response:
   - `docker exec supabase_db_The-Listening-Tree psql -U postgres -d postgres -c 'select 1;'`
6. If full `supabase start` fails due non-DB service health (for example storage), continue local backend work with DB-only mode.

If session is unstable:
1. Confirm production has fixed `SECRET_KEY`.
2. Ensure HTTPS is used.
3. Clear browser cookies and retry.

## 9. Branch strategy (recommended)

- `main`: production deploy branch
- `develop`: integration branch
- feature branches -> PR -> CI -> merge to `main`

## 10. Security baseline

- Never commit `.env` files.
- Rotate `VERCEL_TOKEN` and API keys periodically.
- Use least-privilege DB credentials.
- Keep dependencies updated (`pip list --outdated`, `npm outdated`).
