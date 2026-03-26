# The Listening Tree 🌳

**Compassionate AI Companion for Elderly Wellness**

A bilingual (English + Cantonese) conversational chatbot designed to reduce loneliness and improve wellness in elderly populations. Powered by Zhipu AI (GLM-4), featuring voice interaction, medication reminders, memory games, and Hong Kong holiday calendar.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/fastapi-0.115.12-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![License](https://img.shields.io/badge/license-Academic-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-production-brightgreen)](#deployment)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Key Features](#key-features)
3. [Quick Start](#quick-start)
4. [Usage](#usage)
5. [Configuration](#configuration)
6. [Project Structure](#project-structure)
7. [Development](#development)
8. [Deployment](#deployment)
9. [FAQ](#faq)
10. [Contributing](#contributing)
11. [License](#license)
12. [Contact](#contact)

---

## Introduction

### What is The Listening Tree?

**The Listening Tree** is an AI-powered elderly companion chatbot that bridges the loneliness gap through warm, natural conversations. It provides:
- **Conversational AI** for daily social interaction using Zhipu's GLM-4 LLM
- **Voice-first interface** with Web Speech API (English & Cantonese)
- **Smart reminders** for medications, activities, and social engagement
- **Cognitive games** to stimulate memory and mental health
- **Accessible design** with WCAG AA compliance, large UI elements, and high-contrast modes
- **Bilingual support** with seamless English ↔ Cantonese switching

### Problem Solved

Elderly populations often experience social isolation due to mobility limitations or family distance. This chatbot provides a persistent, judgment-free companion available 24/7.

### Use Cases

- **Daily Wellness Monitoring** – Medication reminders and activity tracking
- **Cognitive Engagement** – Trivia games and memory quizzes
- **Social Interaction** – Warm, patient conversation in preferred language
- **Information Access** – Hong Kong public holidays, local news, weather
- **Accessibility First** – Works on web, iOS, and Android with minimal technical knowledge

### Technology Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Bootstrap 5, FullCalendar.js, Web Speech API, Capacitor (iOS/Android) |
| **Backend** | FastAPI (Python 3.12), async/await for real-time responsiveness |
| **LLM** | Zhipu AI `glm-4-flash` (bilingual, low-latency) |
| **Database** | PostgreSQL (production) / SQLite (local dev) |
| **Deployment** | Docker, Vercel, Render, or VPS |
| **Session Management** | itsdangerous secure cookies with fixed SECRET_KEY |

---

## Key Features

| Feature | Details |
|---------|---------|
| **Warm Conversation** | Zhipu AI `glm-4-flash` with patient, compassionate responses tailored for elderly |
| **Voice I/O** | Web Speech API for English & Cantonese; optional Vosk offline fallback |
| **Smart Calendar** | FullCalendar.js with Hong Kong public holidays (2025–2027) |
| **Persistent Reminders** | Medication, activity, and social reminders stored in PostgreSQL |
| **Memory Games** | Bilingual trivia and word-recall quizzes for cognitive engagement |
| **News & Updates** | NewsAPI integration with hardcoded HK news fallback |
| **Accessible Design** | WCAG AA compliance: 48px touch targets, keyboard navigation, dark/light modes |
| **Bilingual** | Full English + Cantonese (zh-HK) with real-time language switching |
| **Responsive** | 3-column desktop → stacked mobile layout (iOS/Android via Capacitor) |
| **Offline-First** | Works without external dependencies; all voice processing optional |

---

## Quick Start

### 4.1 Environment Requirements

**System:**
- macOS, Linux, or Windows with WSL 2
- 2GB RAM minimum (4GB recommended for LLM inference)

**Software:**
- **Python 3.12+** (check: `python --version`)
- **Node.js 18+** (for mobile app; optional for web-only) (check: `node --version`)
- **Git** (check: `git --version`)
- **PostgreSQL** (cloud: Supabase / Neon; local: `brew install postgresql` on macOS)
- **Docker** (optional; recommended for containerized deployment)

### 4.2 Installation Steps

#### A) Clone the Repository

```bash
git clone https://github.com/Brian-code-123/The-Listening-Tree.git
cd The-Listening-Tree
```

#### B) Create Virtual Environment

```bash
# Create Python virtual environment
python -m venv .venv

# Activate
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows
```

#### C) Install Dependencies

```bash
pip install -r requirements.txt
# Optional: pip install -r requirements-local.txt  (includes Vosk for offline STT)
```

#### D) Configure Environment Variables

Create a `.env` file in the project root:

```bash
cat > .env << 'EOF'
# Zhipu AI (required)
ZHIPU_API_KEY="<your-api-key>"
ZHIPU_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
ZHIPU_MODEL="glm-4-flash"

# Database (required for production)
DATABASE_URL="postgresql://<user>:<password>@<host>:5432/<dbname>"

# Session security (required for production)
SECRET_KEY="<64-char-hex-string>"

# Optional: News API
NEWS_API_KEY="<your-newsapi-key>"

# Server
PORT="5000"
EOF
```

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

#### E) Initialize Database

The database tables are auto-created on first run. For local development, you can use SQLite:

```bash
# The app will auto-create reminders.db on startup if DATABASE_URL is not set
python run.py  # Starts on http://localhost:5000
```

#### F) Access the Application

- **Web:** Open browser → `http://localhost:5000`
- **Mobile (iOS):** `npm run cap:ios` (requires Node.js + Capacitor)
- **Mobile (Android):** `npm run cap:android`

---

## Usage

### 5.1 Chat & Conversation

1. **Type or speak:** Use the chat box or click the microphone icon
2. **Get response:** Zhipu AI responds within 2–5 seconds
3. **Switch language:** Click the language toggle (EN ↔ 粵語)

Example dialogue:
```
You:  "Good morning, how are things today?"
Bot:  "Good morning! I'm glad to see you. How has your day been so far?"
```

### 5.2 Set a Reminder

Command: `"set reminder [activity] [HH:MM]"`

Examples:
```
"set reminder take medicine 09:00"
"set reminder exercise 14:30"
"set reminder call daughter 18:00"
```

The bot will confirm and store in the database. Reminders trigger at the specified time (UI alert).

### 5.3 Delete a Reminder

Command: `"delete reminder [activity]"`

Example:
```
"delete reminder take medicine"
```

### 5.4 Play a Game

Command: `"play game"`

The bot starts a trivia quiz. Answer with keywords (case-insensitive, partial match):
```
Bot:  "What is the capital of France?"
You:  "paris"  # Auto-accepted (partial match)
Bot:  "✅ Correct! Next question..."
```

### 5.5 View Calendar & Holidays

Click the **Calendar** tab to see:
- Hong Kong public holidays (2025–2027)
- Your scheduled reminders
- Click a date to see details

### 5.6 News & Updates

Click the **News** tab to read:
- Latest HK news (from NewsAPI or hardcoded fallback)
- Updated every 30 minutes

### 5.7 Accessibility Features

- **Large Text Mode:** Click Settings → Accessibility
- **High Contrast:** Toggle dark/light theme
- **Keyboard Navigation:** Tab through buttons, Enter to activate
- **Screen Reader Friendly:** HTML semantic structure + ARIA labels

---

## Configuration

### 6.1 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ZHIPU_API_KEY` | **Yes** | — | Zhipu AI API key from [open.bigmodel.cn](https://open.bigmodel.cn) |
| `ZHIPU_BASE_URL` | No | `https://open.bigmodel.cn/api/paas/v4` | Zhipu API endpoint |
| `ZHIPU_MODEL` | No | `glm-4-flash` | LLM model identifier |
| `DATABASE_URL` | **Yes** | — | PostgreSQL connection string: `postgresql://user:password@host:5432/dbname` (use Supabase, Neon, or Docker) |
| `SECRET_KEY` | **Yes** | — | 64-char hex session signing key. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `NEWS_API_KEY` | No | — | NewsAPI key for live news (falls back to hardcoded article list) |
| `PORT` | No | `5000` | Server port |

### 6.2 Database Setup

**Option 1: Supabase (Cloud, Recommended)**

1. Sign up at [supabase.co](https://supabase.co)
2. Create new project → copy connection string
3. In `.env`: `DATABASE_URL="postgresql://postgres:<password>@..."`

**Option 2: Neon (Cloud, Free Tier)**

1. Sign up at [neon.tech](https://neon.tech)
2. Create compute → get connection URL
3. In `.env`: `DATABASE_URL="postgresql://..."`

**Option 3: Local Docker**

```bash
docker run -d --name postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=yourpassword \
  -e POSTGRES_DB=listening_tree \
  -p 5432:5432 \
  postgres:15
```

Then: `DATABASE_URL="postgresql://postgres:yourpassword@localhost:5432/listening_tree"`

### 6.3 Database Auto-initialization

The application creates tables automatically on first run:
- `users` (email, password_hash, created_at)
- `reminders` (user_id, activity, time, priority, is_active)
- `chat_history` (user_id, message, sender, timestamp, language)
- `preferences` (user_id, language, theme, notification_enabled)

### 6.4 SQLite → PostgreSQL Migration (Optional)

If migrating from an existing SQLite database:

```bash
export SQLITE_PATH="reminders.db"
export DATABASE_URL="postgresql://..."
python scripts/migrate_sqlite_to_postgres.py
```

This script transfers all users, reminders, and chat history to PostgreSQL.

---

## Project Structure

```
The-Listening-Tree/
│
├── run.py                         # Main FastAPI application (entry point)
├── translations.py                # Bilingual strings (EN + zh-HK)
├── requirements.txt               # Production Python dependencies
├── requirements-local.txt         # Dev dependencies (includes Vosk)
├── Dockerfile                     # Docker build configuration
├── vercel.json                    # Vercel deployment routing config
├── capacitor.config.ts            # iOS/Android app config
├── package.json                   # Node.js dependencies (for mobile)
├── .env.example                   # Environment variables template
├── LICENSE                        # Academic use license
│
├── api/
│   └── index.py                   # Vercel serverless entry point
│
├── templates/
│   ├── chat.html                  # Main chat UI (glassmorphism design)
│   ├── login.html                 # User login form
│   ├── register.html              # User registration form
│   └── accessibility.html         # Large-text accessible mode
│
├── static/
│   └── style.css                  # Responsive theme (dark/light modes)
│
├── assets/
│   └── [icons & images]
│
├── ios/                           # Native iOS app files (Xcode project)
│   └── App/
│       ├── App.xcodeproj
│       ├── AppDelegate.swift
│       └── public/index.html
│
├── android/                       # Native Android app files
│   ├── app/src/main/
│   └── build.gradle
│
└── [cache folders - safe to delete]
    ├── __pycache__/               # Python cache (auto-generated)
    ├── .pytest_cache/             # Pytest cache (auto-generated)
    ├── node_modules/              # npm packages (auto-generated)
    └── build/                     # iOS build artifacts (auto-generated)
```

### Key Files Explained

| File | Purpose |
|------|---------|
| `run.py` | FastAPI routes, LLM inference, database queries, reminder scheduling |
| `translations.py` | i18n dictionary for English & Cantonese messages |
| `chat.html` | Main UI with microphone button, message history, language toggle |
| `style.css` | Glassmorphism design, responsive grid, dark/light themes |
| `.env.example` | Copy to `.env` and fill in real credentials |
| `vercel.json` | Routes `/api/*` to FastAPI routes; public folders for static files |
| `Dockerfile` | Multi-stage build: dependencies → runtime image (optimized size) |

---

## Development

### 7.1 Code Standards

**Python Style:**
- Follow PEP 8 (4-space indentation)
- Type hints for function signatures
- Docstrings for public functions
- Use async/await for I/O-bound operations

Check code style:
```bash
flake8 run.py translations.py --max-line-length=100
```

**Frontend:**
- Use semantic HTML (nav, section, main)
- Mobile-first responsive design
- WCAG AA accessibility (color contrast, focus states)

### 7.2 Git Commit Conventions

```
feat:       New feature (e.g., "feat: add mood tracking")
fix:        Bug fix (e.g., "fix: correct reminder time parsing")
refactor:   Code restructure (e.g., "refactor: extract LLM logic")
docs:       Documentation (e.g., "docs: update README")
style:      Formatting, whitespace (e.g., "style: format code")
test:       Tests (e.g., "test: add reminder validation")
ci:         CI/CD or deployment (e.g., "ci: update Docker config")
```

Example:
```bash
git commit -m "feat: add emotion detection for bot responses"
```

### 7.3 Branch Management

- **`main`** – Production-ready code; protected branch, requires PR reviews
- **`develop`** – Integration branch for features
- **`feature/xyz`** – Feature branches (e.g., `feature/emotion-detection`)
- **`bugfix/xyz`** – Bug fix branches (e.g., `bugfix/reminder-timezone`)

Workflow:
```bash
# Create and switch to feature branch
git checkout -b feature/your-feature

# Push and open PR
git push origin feature/your-feature

# After review, merge to main (via GitHub UI)
```

### 7.4 Local Development

```bash
# Start in watch mode with auto-reload
uvicorn run:app --reload --port 5000 --host 0.0.0.0

# Run linting
flake8 run.py --max-line-length=100

# Run tests (if setup)
pytest tests/

# Check imports and dependencies
pip check

# Generate SECRET_KEY for testing
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Deployment

### 8.1 Staging Environment (Render.com)

Render provides free-tier PostgreSQL and Python hosting:

1. **Push to GitHub** (ensure `run.py`, `requirements.txt`, `Dockerfile` are present)

2. **Create Web Service on Render:**
   - Visit [render.com](https://render.com) → New → Web Service
   - Connect GitHub repo
   - Select `The-Listening-Tree` repo

3. **Configure Service:**
   - **Name:** `listening-tree-staging`
   - **Region:** Singapore (or nearest to users)
   - **Branch:** `develop`
   - **Build Command:** (auto-detect if Dockerfile exists)
   - **Start Command:** `gunicorn -w 2 -k uvicorn.workers.UvicornWorker run:app`

4. **Add Environment Variables:**
   - `ZHIPU_API_KEY` = your-key
   - `DATABASE_URL` = (auto-provisioned PostgreSQL or external Supabase URL)
   - `SECRET_KEY` = 64-char hex
   - `NEWS_API_KEY` = (optional)

5. **Deploy:**
   - Render auto-deploys on `git push develop`

### 8.2 Production Deployment (Vercel + Supabase)

Vercel serverless + Supabase PostgreSQL = zero-config production setup.

1. **Push code to GitHub:**
   ```bash
   git push origin main
   ```

2. **Deploy on Vercel:**
   ```bash
   npx vercel --prod
   ```
   Or via [vercel.com](https://vercel.com): Import GitHub repo → Link → Deploy

3. **Set Environment Variables in Vercel Console:**
   - `ZHIPU_API_KEY`
   - `SECRET_KEY`
   - `DATABASE_URL` (Supabase connection string)
   - `NEWS_API_KEY` (optional)

4. **Verify Deployment:**
   ```bash
   curl https://<your-project>.vercel.app/health/db
   # Expected: {"ok": true, "backend": "postgres"}
   ```

### 8.3 Docker Deployment (VPS / Self-Hosted)

1. **Build image:**
   ```bash
   docker build -t listening-tree:latest .
   ```

2. **Run container:**
   ```bash
   docker run -d \
     --name listening-tree \
     -p 5000:5000 \
     -e ZHIPU_API_KEY="your-key" \
     -e DATABASE_URL="postgresql://..." \
     -e SECRET_KEY="<64-char-hex>" \
     listening-tree:latest
   ```

3. **Use Docker Compose (recommended):**
   ```yaml
   # docker-compose.yml
   version: '3.8'
   services:
     app:
       build: .
       ports:
         - "5000:5000"
       environment:
         ZHIPU_API_KEY: "${ZHIPU_API_KEY}"
         DATABASE_URL: "postgresql://postgres:password@postgres:5432/listening_tree"
       depends_on:
         - postgres
     
     postgres:
       image: postgres:15
       environment:
         POSTGRES_USER: postgres
         POSTGRES_PASSWORD: password
         POSTGRES_DB: listening_tree
       volumes:
         - postgres_data:/var/lib/postgresql/data
   
   volumes:
     postgres_data:
   ```

   Deploy:
   ```bash
   docker-compose up -d
   ```

### 8.4 iOS/Android Mobile App Deployment

1. **Build web version first** (test on web before mobile)

2. **Install Capacitor dependencies:**
   ```bash
   npm install
   npm run cap:sync
   ```

3. **iOS (on macOS):**
   ```bash
   npm run cap:open:ios
   # Opens Xcode; configure signing & provisioning profiles
   # Product → Archive → Distribute to TestFlight or App Store
   ```

4. **Android:**
   ```bash
   npm run cap:open:android
   # Opens Android Studio; configure signing key
   # Build → Generate Signed Bundle
   ```

---

## FAQ

### Q: How do I add a new reminder command?
**A:** Edit `run.py`, locate the command parser in `/get_response` route. Add a new condition:
```python
if user_input.startswith("remind me"):
    # Parse and store reminder
```
Commit: `git commit -m "feat: add custom reminder pattern"`

### Q: Can I change the LLM provider (e.g., from Zhipu to OpenAI)?
**A:** Yes. Replace the `zhipu_api_call()` function in `run.py` with your provider's SDK. Ensure the response format is compatible (should return plain text string).

### Q: How do I deploy without cloud (e.g., on a Raspberry Pi)?
**A:** Use Docker + Compose. The app runs on RPi 4 (2GB+ RAM), though LLM inference will be slow. Consider using a smaller model or offload to cloud APIs.

### Q: Is my conversation data encrypted?
**A:** No. To add encryption:
1. Use PostgreSQL's `pgcrypto` extension
2. Encrypt message content before storing to DB
3. Decrypt on retrieval

### Q: How do I customize the UI colors or fonts?
**A:** Edit `static/style.css`. The design uses CSS variables for easy theming:
```css
:root {
  --primary-color: #007bff;
  --font-family: "Segoe UI", sans-serif;
}
```

### Q: Can I run this for multiple organizations (multi-tenant)?
**A:** The current schema assumes single-tenant. To multi-tenant:
1. Add `organization_id` to all tables
2. Filter queries by `organization_id`
3. Isolate reminders/chat per tenant

### Q: Why does voice transcription sometimes fail?
**A:** 
- Noisy environment → use quieter space
- Browser permissions → check microphone access (browser Settings → Permissions)
- Network latency → if using server-side Vosk (rare)

### Q: How do I update the Hong Kong holidays list?
**A:** Hardcoded holidays are in `run.py` under `/get_hk_holidays`. Update the list and redeploy.

---

## Contributing

### How to Report Issues

1. **GitHub Issues:** Visit [github.com/.../issues](https://github.com/Brian-code-123/The-Listening-Tree/issues)
2. **Format:**
   ```
   **Title:** [Feature/Bug] Brief description
   
   **Description:** What happened? What did you expect?
   
   **Steps to reproduce:**
   1. Step 1
   2. Step 2
   
   **Environment:** OS, Python version, browser
   ```

### How to Submit a Pull Request

1. **Fork** the repository
2. **Create feature branch:** `git checkout -b feature/xyz`
3. **Make changes** (follow code standards above)
4. **Test locally:** Run the app, verify functionality
5. **Commit:** `git commit -m "feat: description"`
6. **Push:** `git push origin feature/xyz`
7. **Open PR** on GitHub with:
   - Title: e.g., "Add mood detection to bot responses"
   - Description: What changes, why, what it fixes/adds
   - Reviewers: Tag @Brian-code-123 for review

### Code Review Checklist

- [ ] Code follows PEP 8 / style guidelines
- [ ] Tests pass (if applicable)
- [ ] No hardcoded credentials or secrets
- [ ] Documentation updated
- [ ] Commit messages follow conventions

---

## License

**Academic Use Only** – Educational and research applications permitted. See [LICENSE](LICENSE) for full terms.

- **Permitted:** Research, classroom projects, non-profit organizations
- **Not Permitted:** Commercial sales, proprietary products, paid services without permission

To request commercial license, contact the creator.

---

## Contact

**Creator:** [Brian Hong](https://github.com/Brian-code-123)

**Get in Touch:**
- 🐙 GitHub: [@Brian-code-123](https://github.com/Brian-code-123)
- 💬 Email: brian.code.123@gmail.com
- 📚 Project Wiki: [GitHub Wiki](https://github.com/Brian-code-123/The-Listening-Tree/wiki)

**Report Bugs:** [GitHub Issues](https://github.com/Brian-code-123/The-Listening-Tree/issues)

---

## Acknowledgments

- **Zhipu AI** (GLM-4) for LLM inference
- **FastAPI** and **Uvicorn** for async web framework
- **PostgreSQL** + **Supabase** for reliable data persistence
- **Bootstrap 5** for responsive UI
- **FullCalendar.js** for calendar widget
- **Capacitor** for cross-platform mobile support

---

**Made with ❤️ for elderly wellness | 2025–2026**
# Fix deployed at: Thu Mar 26 01:38:42 HKT 2026
