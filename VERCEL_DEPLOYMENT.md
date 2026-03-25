# Vercel Deployment Guide for The Listening Tree

This guide provides step-by-step instructions to deploy **The Listening Tree** Chatbot to Vercel with production database support.

**Status**: Code is ready for deployment ✅  
**Last Updated**: March 26, 2026  
**Required Time**: ~10–15 minutes

---

## 📋 Prerequisites

Before deploying, ensure you have:

- [ ] [Vercel Account](https://vercel.com) (free tier supported)
- [ ] [GitHub Account](https://github.com) with repository access
- [ ] [PostgreSQL Database URL](#step-1-obtain-postgresql-database-url) (Supabase, Neon, Railway, or custom)
- [ ] Local environment with Python 3.9+ and FastAPI dependencies
- [ ] `vercel` CLI installed locally (`brew install vercel` on macOS)

---

## Step 1: Obtain PostgreSQL Database URL

The application requires a PostgreSQL database for production. Choose one:

### Option A: Supabase (Recommended)
Best for beginners; includes free tier.

1. Go to [supabase.com](https://supabase.com) → Sign up
2. Create a new project
3. In Settings → Database, find the **Connection Pooling URL** (use Transaction mode)
4. Copy the URL:
   ```
   postgresql://postgres.[PROJECT_ID]:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   ```

### Option B: Neon PostgreSQL
Fast, serverless PostgreSQL.

1. Go to [neon.tech](https://neon.tech) → Sign up
2. Create a new project
3. Copy the connection string from the dashboard:
   ```
   postgresql://user:password@ep-[ID].ng.neon.tech:5432/neondb?sslmode=require
   ```

### Option C: Railway
Simple PostgreSQL hosting with Docker support.

1. Go to [railway.app](https://railway.app) → Sign up via GitHub
2. Create a PostgreSQL plugin
3. Copy the connection URL from the variable panel

### Option D: Custom PostgreSQL
If you have your own Postgres server:
```
postgresql://[USER]:[PASSWORD]@[HOST]:[PORT]/[DATABASE]
```

---

## Step 2: Prepare Local Environment

### 2.1 Verify Code is Ready

```bash
cd /Users/lochunman/Desktop/個人項目/The-Listening-Tree

# Check git status
git status

# Verify latest commits
git log --oneline -3
```

Expected output (commits with "fix: harden serverless" and "fix: make db fallback"):
```
dde667f3 fix: make db fallback and lifespan serverless-safe
65f26036 fix: harden serverless startup and add health probes
...
```

### 2.2 Create `.env.production` (for reference)

This file is **NOT committed to Git**; it documents what will be set in Vercel:

```bash
# .env.production (DO NOT COMMIT — reference only)
ZHIPU_API_KEY=65268f3fb62b4d5c98f7f9d48003bad0.P1X9OHb6tLnNhdwj
SECRET_KEY=7dea9686bce3d87e71284b7692bee85f6a11361dadc6910cc0761e208f289b59
DATABASE_URL=postgresql://postgres.XXXXX:password@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
ZHIPU_MODEL=glm-4-flash
```

---

## Step 3: Link Project and Set Environment Variables

### 3.1 Authenticate with Vercel CLI

```bash
# Check authentication
vercel whoami
# Expected: lochunman88-8840 (or your Vercel username)

# If not authenticated, run:
vercel login --github
```

### 3.2 Link Project to Vercel

```bash
cd /Users/lochunman/Desktop/個人項目/The-Listening-Tree

# Link the project (interactive)
vercel link

# When prompted:
# ? Set up "./The-Listening-Tree"? → YES
# ? Link to existing project? → YES (if already on Vercel)
#   Or: NO (to create new project)
# ? Project name? → the-listening-tree
```

This creates a `.vercel/` directory with project metadata.

### 3.3 Set Environment Variables in Vercel

#### Using Vercel CLI (Recommended):

```bash
# Add ZHIPU_API_KEY
vercel env add ZHIPU_API_KEY
# Paste: 65268f3fb62b4d5c98f7f9d48003bad0.P1X9OHb6tLnNhdwj
# Select: Production, Preview (or just Production)

# Add SECRET_KEY (CRITICAL for session persistence)
vercel env add SECRET_KEY
# Paste: 7dea9686bce3d87e71284b7692bee85f6a11361dadc6910cc0761e208f289b59
# Select: Production

# Add DATABASE_URL
vercel env add DATABASE_URL
# Paste your PostgreSQL URL from Step 1
# Select: Production

# Optional: Add other variables
vercel env add ZHIPU_BASE_URL
# Paste: https://open.bigmodel.cn/api/paas/v4

vercel env add ZHIPU_MODEL
# Paste: glm-4-flash
```

#### Using Vercel Dashboard (Alternative):

1. Go to [vercel.com](https://vercel.com) → Select your project
2. Settings → Environment Variables
3. Add each variable:
   - **ZHIPU_API_KEY**: `65268f3fb62b4d5c98f7f9d48003bad0.P1X9OHb6tLnNhdwj`
   - **SECRET_KEY**: `7dea9686bce3d87e71284b7692bee85f6a11361dadc6910cc0761e208f289b59`
   - **DATABASE_URL**: Your PostgreSQL connection string
   - **ZHIPU_BASE_URL**: `https://open.bigmodel.cn/api/paas/v4`
   - **ZHIPU_MODEL**: `glm-4-flash`
4. Select **Production** for each
5. Save

### 3.4 Verify Environment Variables

```bash
vercel env list
```

Expected output:
```
ZHIPU_API_KEY              • Encrypted •     Production
SECRET_KEY                 • Encrypted •     Production
DATABASE_URL               • Encrypted •     Production
ZHIPU_BASE_URL             • Encrypted •     Production
ZHIPU_MODEL                • Encrypted •     Production
```

---

## Step 4: Deploy to Vercel

### Option A: Automatic (Recommended)

Push to GitHub; Vercel will automatically deploy:

```bash
git push origin main
```

Check deployment status:
- Vercel Dashboard → Your Project → Recent Deployments
- Or use: `vercel list`

### Option B: Manual Deploy

```bash
# Deploy to production
vercel --prod

# Or from the project directory:
vercel deploy --prod
```

Expected output:
```
✓ Deployed to https://the-listening-tree-xxxx.vercel.app
```

---

## Step 5: Verify Deployment

### 5.1 Test Health Endpoints

```bash
# Check basic health
curl https://the-listening-tree-xxxx.vercel.app/health

# Expected response:
# {"ok":true,"service":"the-listening-tree","backend":"postgres"}

# Check database connectivity
curl https://the-listening-tree-xxxx.vercel.app/health/db

# Expected response:
# {"ok":true,"backend":"postgres"}
```

### 5.2 Test Chat Endpoint (with auth)

```bash
# 1. Register a new user
curl -X POST https://the-listening-tree-xxxx.vercel.app/register \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=test@example.com&password=TestPassword123"

# 2. Login to get session cookie
curl -X POST https://the-listening-tree-xxxx.vercel.app/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=test@example.com&password=TestPassword123" \
  -c cookies.txt

# 3. Send a chat message
curl -X POST https://the-listening-tree-xxxx.vercel.app/get_response \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -b cookies.txt \
  -d "message=Hello"
```

### 5.3 Verify Logs

```bash
# View recent deployment logs
vercel logs https://the-listening-tree-xxxx.vercel.app

# Or from Dashboard:
# Vercel.com → Your Project → Deployments → Latest → Logs
```

---

## Troubleshooting

### Issue: 500 Error on /health

**Cause**: Environment variables not set  
**Solution**:
```bash
vercel env list  # Verify variables are present
vercel deploy --prod  # Redeploy to apply
```

### Issue: Database Connection Fails

**Cause**: Invalid DATABASE_URL  
**Solution**:
1. Verify PostgreSQL URL format (include `?sslmode=require` for cloud databases)
2. Test locally:
   ```bash
   DATABASE_URL="your-url" python -c "import run; run.init_db()"
   ```
3. Update in Vercel:
   ```bash
   vercel env pull  # Get current values
   vercel env add DATABASE_URL  # Update
   vercel deploy --prod
   ```

### Issue: "SECRET_KEY is set"? Change It

If you see warnings about SECRET_KEY in logs:
1. Generate a new one:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Update in Vercel:
   ```bash
   vercel env add SECRET_KEY
   # Paste new value
   ```
3. Redeploy:
   ```bash
   vercel deploy --prod
   ```

### Issue: "psycopg2 is required"

This should NOT happen on Vercel (it's in `requirements.txt`). If it does:
1. Force rebuild:
   ```bash
   vercel deploy --prod --force
   ```

---

## Production Checklist

- [ ] PostgreSQL database created and accessible
- [ ] DATABASE_URL set in Vercel (Production env)
- [ ] ZHIPU_API_KEY configured
- [ ] SECRET_KEY set (fixed, same across deploys)
- [ ] Code pushed to `main` branch
- [ ] `/health` endpoint returns 200 OK
- [ ] `/health/db` endpoint returns 200 OK (backend: postgres)
- [ ] Chat endpoints work (login → message → response)
- [ ] No 500 errors in Vercel logs

---

## Monitoring & Maintenance

### View Logs

```bash
# Stream live logs
vercel logs PROJECT_URL --follow

# View specific deployment
vercel logs PROJECT_URL --since 1h
```

### Update Secrets Safely

```bash
# Pull current environment
vercel env pull

# Update and redeploy
vercel env add SECRET_KEY
vercel deploy --prod
```

### Rollback to Previous Deployment

```bash
vercel list  # Find previous deployment URL
vercel alias SET <URL> the-listening-tree  # Promote old version
```

---

## Additional Resources

- **Vercel Docs**: https://vercel.com/docs/frameworks/python
- **FastAPI on Vercel**: https://vercel.com/docs/serverless-functions/python
- **PostgreSQL Connection Pooling**: https://vercel.com/docs/storage/postgres/usage-guide
- **Supabase Setup**: https://supabase.com/docs/guides/getting-started/quickstarts/python
- **Neon Documentation**: https://neon.tech/docs

---

## Support

If deployment fails:

1. **Check Vercel Logs**:
   ```bash
   vercel logs https://your-project.vercel.app
   ```

2. **Test Locally First**:
   ```bash
   python run.py  # Should start without errors
   ```

3. **Verify All Environment Variables**:
   ```bash
   vercel env list
   ```

4. **Force Full Rebuild**:
   ```bash
   git push origin main
   vercel deploy --prod --force
   ```

---

**Happy deploying! 🚀**
