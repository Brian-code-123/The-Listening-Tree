# The Listening Tree 🌳

> **Compassionate AI Companion for Elderly Wellness**  
> Bilingual chatbot (English + Cantonese) powered by Zhipu AI (GLM-4) LLM, featuring accessible voice interaction, medication reminders, and cognitive games.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/fastapi-0.115.12-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-Academic-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-production-brightgreen)](#deployment)

---

## Overview

**The Listening Tree** is a bilingual companion chatbot designed to reduce loneliness and promote wellness in elderly populations. It integrates Zhipu AI (GLM-4) for natural conversation, reminders, memory games, Hong Kong public holidays, and local news—all wrapped in an accessible, elderly-friendly glassmorphism UI.

**Built with:** FastAPI (async Python) → Zhipu AI `glm-4-flash` LLM → **PostgreSQL (production)** persistence → Bootstrap 5 + FullCalendar.js frontend + Capacitor Mobile App.

---

## Key Features

| Feature | Details |
|---------|---------|
| **Warm LLM Chat** | Zhipu AI (`glm-4-flash`) with patient, elderly-tailored conversation |
| **Voice I/O** | Web Speech API for English & Cantonese (zero server deps); optional Vosk offline fallback |
| **Smart Calendar** | FullCalendar.js with Hong Kong public holidays (2025–2027) |
| **Persistent Reminders** | SQLite (local dev) or PostgreSQL/Supabase (production) medication, activity, and social reminders |
| **Memory Games** | Bilingual trivia & recall quizzes for cognitive engagement |
| **News Feed** | NewsAPI.org integration with hardcoded HK news fallback |
| **Accessible Design** | WCAG AA compliance, 48px touch targets, keyboard navigation, dark/light modes |
| **Bilingual** | Full English + Cantonese (zh-HK) with live language switching |
| **Responsive** | 3-column desktop layout → stacked mobile layout |

---

## Quick Start

### Prerequisites

- **Python 3.12+** or Docker
- **Tencent Hunyuan API Key** ([Get free credits](https://www.tencentcloud.com/products/hunyuan))
- Modern browser (Chrome, Edge, Safari 14.1+)

### Local Development

```bash
# Clone
git clone https://github.com/Brian-code-123/The-Listening-Tree.git
cd The-Listening-Tree

# Virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# Optional: pip install -r requirements-local.txt  (includes Vosk for offline STT)

# Configure environment
cat > .env << EOF
ZHIPU_API_KEY="your-zhipu-api-key"
ZHIPU_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
ZHIPU_MODEL="glm-4-flash"
NEWS_API_KEY="your-newsapi-key"  # Optional
EOF

# Run Backend
python run.py
# Open on Web: http://localhost:5000
# Or run Capacitor Mobile App: npm run cap:open:ios
```

### Docker

```bash
docker build -t the-listening-tree .
docker run -p 5000:5000 \
  -e ZHIPU_API_KEY="your-key" \
  the-listening-tree
```

### Vercel Deployment (Detailed)

We added `vercel.json` and a Vercel serverless entry at `api/index.py` so the Vercel Python builder can find your FastAPI `app`.

Two ways to deploy: A) Git-based (recommended for CI), or B) CLI (quick manual deploy).

1) GitHub → Vercel (automatic builds)

- Push your code (make sure `vercel.json` and `api/index.py` are committed):

```bash
git add vercel.json api/index.py README.md
git commit -m "chore: add vercel config + serverless entrypoint"
git push origin main
```

- On vercel.com choose **Import Project** → select your GitHub repo → when prompted set:
  - **Root Directory**: `.` (project root)
  - **Build & Output Settings**: leave empty for Python (Vercel will detect `api/index.py`)
  - Add Environment Variables in Project Settings: `ZHIPU_API_KEY`, `SECRET_KEY`, and optionally `DATABASE_URL`.

- Vercel will run automatic builds on each push. If you saw a build failure like "No fastapi entrypoint found", ensure `api/index.py` and `vercel.json` exist in the repository and that the commit was pushed.

2) Quick deploy from your machine (CLI) — no global install required (use `npx`)

- Login (one-time):

```bash
npx vercel@latest login
```

- Deploy from project root (interactive) or use `--prod` for production:

```bash
cd /path/to/The-Listening-Tree
npx vercel@latest --prod
```

- Notes:
  - If you get a prompt to select a project, choose to create or link to the correct project.
  - `npx` avoids global `npm` permission problems.

3) Fixing `npm` global permission errors (optional)

- If you prefer globally installing `vercel` but got `EACCES` errors, create a local npm global folder:

```bash
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=$HOME/.npm-global/bin:$PATH' >> ~/.zshrc
source ~/.zshrc
npm install -g vercel
```

- Or use `sudo npm install -g vercel` (not recommended due to permission/security concerns).

4) What we added to this repo

- `vercel.json` — routing/build override to help Vercel find the FastAPI app.
- `api/index.py` — serverless entrypoint that dynamically loads `fastapi/main.py` and exposes `app` to Vercel's Python runtime.

5) Troubleshooting

- Build failed: "No fastapi entrypoint found" → confirm `api/index.py` and `vercel.json` are present in the default branch pushed to GitHub.
- 500 / runtime errors → check Vercel build logs and the function logs (Vercel Console → Deployments → Logs). Missing Python packages will show in build logs; add them to `requirements.txt` in the repo root or in `fastapi/requirements.txt` (we included a minimal `fastapi/requirements.txt`).

6) Quick verification

- After deploy, test the endpoints (replace with your prod domain):

```bash
curl https://<your-project>.vercel.app/api/data
curl https://<your-project>.vercel.app/
```


---

## Architecture

```
Browser / iOS / Android (Bootstrap 5 + FullCalendar + Web Speech API)
       ↓ AJAX/JSON/FormData
FastAPI (async Python)
       ├─ POST /get_response     → Command parser → Zhipu LLM
       ├─ POST /transcribe       → Vosk STT (optional)
       ├─ GET /get_reminders     → Active reminders for today
       ├─ GET /get_chat_history  → Per-user, per-language messages
       ├─ GET /get_hk_holidays   → Static holiday dataset
       ├─ GET /get_news          → NewsAPI + 30-min cache
       └─ Auth routes            → /login, /register, /logout
       ↓
SQLite (users, reminders, chat_history, preferences)
```

---

## Technology Stack

| Component | Package | Version | Purpose |
|-----------|---------|---------|---------|
| **Framework** | FastAPI | 0.115.12 | Async ASGI web framework |
| **Server** | Uvicorn | 0.34.2 | ASGI server |
| **Process Manager** | Gunicorn | 23.0.0 | Production process manager |
| **LLM** | Zhipu AI | glm-4-flash | Conversational System |
| **Database** | PostgreSQL | Supabase / Neon / Custom | Production-grade data persistence (users, reminders, chat, preferences) |
| **HTTP Client** | httpx | 0.28.1 | Async requests to Zhipu & NewsAPI |
| **Templates** | Jinja2 | 3.1.6 | Server-side HTML rendering |
| **Session Auth** | itsdangerous | 2.2.0 | Secure cookies |
| **Env Config** | python-dotenv | 1.0.0 | .env file loading |
| **Voice (Optional)** | Vosk | 0.3.45 | Offline English STT |
| **Mobile App** | Capacitor | 6.2 | iOS / Android Native Wrapper |
| **Frontend** | Bootstrap | 5.3.2 | Responsive UI |
| **Calendar** | FullCalendar.js | 6.1 | Interactive calendar widget |

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ZHIPU_API_KEY` | Yes | — | Zhipu AI API key |
| `ZHIPU_BASE_URL` | No | `https://open.bigmodel.cn/api/paas/v4` | Zhipu endpoint |
| `ZHIPU_MODEL` | No | `glm-4-flash` | Model name |
| `NEWS_API_KEY` | No | — | NewsAPI key (falls back to hardcoded articles) |
| `DATABASE_URL` | **Yes** | — | **PostgreSQL connection string** (required). Example: `postgresql://user:pass@host:5432/dbname` Use Supabase, Neon, or other provider. |
| `SECRET_KEY` | **Yes** | — | **64-char hex string** for session signing. Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` Must be fixed per deployment environment. |
| `PORT` | No | `5000` | Server port |

### Database

PostgreSQL tables auto-created on startup:
- **users** – Email, password, created_at, last_login
- **reminders** – Per-user medication/activity reminders with time, priority
- **chat_history** – Per-user, per-language messages (soft-deleted after 30 min)
- **preferences** – User settings (language, etc.)

For production (Vercel), use managed PostgreSQL: [Supabase](https://supabase.co), [Neon](https://neon.tech), or equivalent.

### SQLite → PostgreSQL Migration

If migrating from SQLite, use the provided migration script:

```bash
export SQLITE_PATH=reminders.db
export DATABASE_URL='postgresql://user:pass@host:5432/dbname'
python scripts/migrate_sqlite_to_postgres.py
```

This will transfer all user data, reminders, and chat history to PostgreSQL.

### Health Check

After deployment, verify database connectivity:

```bash
curl https://<your-app>.vercel.app/health/db
```

Expected response (if successful):
```json
{"ok": true, "backend": "postgres"}
```

---

## Project Structure

```
The-Listening-Tree/
├── run.py                    # Main FastAPI application
├── translations.py           # Bilingual i18n strings (EN + zh-HK)
├── requirements.txt          # Production dependencies
├── requirements-local.txt    # Dev dependencies (+ Vosk)
├── Dockerfile                # Docker build config
├── vercel.json               # Vercel routing
├── .env.example              # Environment template
│
├── api/
│   └── index.py              # Vercel serverless entry point
│
├── templates/
│   ├── chat.html             # Main chat UI (glassmorphism)
│   ├── login.html            # Login form
│   ├── register.html         # Registration form
│   └── accessibility.html    # WCAG AAA large-text mode
│
└── static/
    └── style.css             # Responsive theme (dark/light)
```

---

## Command Syntax

### Reminders
- **Set:** `"set reminder take medicine 09:00"`
- **Delete:** `"delete reminder take medicine"`

### Games
- **Start:** `"play game"`
- **Answer:** Type answer (case-insensitive partial matching)
- **Exit:** `"exit game"`

### Default
- Any input not matching above commands is sent to Tencent Hunyuan LLM with warm system prompt.

---

## Deployment Options

### Render (Recommended)

1. Push to GitHub  
2. Create Web Service on Render, connect GitHub repo  
3. Set Start Command: `gunicorn -w 4 -b 0.0.0.0:5000 -k uvicorn.workers.UvicornWorker run:app`  
4. Add environment variables  
5. Deploy  

### VPS / Docker

```bash
docker build -t listening-tree .
docker run -d -p 5000:5000 \
  -e HUNYUAN_API_KEY="..." \
  -v elder-data:/app \
  listening-tree
```

### Vercel

See **Quick Start** section. Use external DB for persistence.

---

## Development

```bash
# Verify setup
python -c "from run import app; print('✅ FastAPI app loaded')"

# Local dev with auto-reload
uvicorn run:app --reload --port 5000

# Check lint  
flake8 run.py translations.py --max-line-length=100
```

### Commit Conventions

```
feat:     New feature
fix:      Bug fix
refactor: Code restructure
docs:     Documentation
style:    Formatting / whitespace
perf:     Performance improvement
ci:       CI/CD / deployment config
```

---

## License

**Academic Use Only** – Educational and research applications permitted. See [LICENSE](LICENSE) for full terms. Commercial use requires permission from developers.


---

**Built with ❤️ 2026**
