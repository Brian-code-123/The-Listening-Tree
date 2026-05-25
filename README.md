# The Listening Tree 🌳

**Compassionate AI Companion Chatbot for Elderly Wellness**

A bilingual (English + Cantonese) conversational AI chatbot designed to reduce loneliness and improve wellness for elderly populations. Built with FastAPI backend, Zhipu AI LLM integration, and responsive web/mobile UI using Capacitor for iOS and Android.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/fastapi-0.115.12-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Zhipu AI](https://img.shields.io/badge/LLM-Zhipu%20GLM--4-blue?logo=openai&logoColor=white)](https://open.bigmodel.cn)
[![License](https://img.shields.io/badge/license-Academic-orangered.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-stable-brightgreen)](https://github.com/Brian-code-123/The-Listening-Tree)

---

## Table of Contents

1. [Overview](#overview)
   - [What is The Listening Tree?](#what-is-the-listening-tree)
   - [Problem & Solution](#problem--solution)
   - [Key Statistics](#key-statistics)

2. [Technology Stack](#technology-stack)
   - [Backend Architecture](#backend-architecture)
   - [Frontend Architecture](#frontend-architecture)
   - [Database Schema](#database-schema)

3. [API Endpoints](#api-endpoints)
   - [Authentication Routes](#authentication-routes)
   - [Chat & Conversation](#chat--conversation)
   - [Reminders Management](#reminders-management)
   - [Health & Diagnostics](#health--diagnostics)

4. [Features](#features)

5. [Quick Start](#quick-start)
   - [Prerequisites](#prerequisites)
   - [Installation](#installation)
   - [Configuration](#configuration)
   - [Running Locally](#running-locally)

6. [Usage](#usage)
   - [Text Chat](#text-chat)
   - [Voice Interaction](#voice-interaction)
   - [Reminders](#reminders)
   - [Games](#games)
   - [Calendar](#calendar)

7. [Project Structure](#project-structure)

8. [Development](#development)
   - [Code Standards](#code-standards)
   - [Testing](#testing)
   - [Git Workflow](#git-workflow)

9. [Deployment](#deployment)
   - [Web (Vercel / Render)](#web-vercel--render)
   - [Mobile (iOS / Android)](#mobile-ios--android)
   - [Docker Self-Hosted](#docker-self-hosted)

10. [Troubleshooting & FAQ](#troubleshooting--faq)


11. [License](#license)

---

## Overview

### What is The Listening Tree?

**The Listening Tree** is an AI-powered companion chatbot specifically designed for elderly populations to combat loneliness and improve mental wellness through daily conversation and activity engagement.

**Core Capabilities:**
- 🤖 **Conversational AI** – Warm, bilingual dialogue via Zhipu AI GLM-4 LLM, guided by a curated persona prompt and short-turn conversational memory
- 🎤 **Voice Interaction** – Browser-based Web Speech API for hands-free chat (English & Cantonese)
- 📱 **Cross-Platform** – Web, iOS (native), Android (native) via Capacitor
- 💊 **Smart Reminders** – Medicine schedules, activity tracking, social engagement prompts
- 🧠 **Cognitive Games** – Bilingual trivia and memory quizzes
- 📅 **Calendar** – Hong Kong public holidays, event tracking
- 🌍 **Localized News** – HK news feed with NewsAPI fallback
- ♿ **Accessibility** – WCAG AA compliance: large buttons, high contrast, keyboard navigation
- 🌐 **Bilingual** – Seamless English ↔ Cantonese (zh-HK) switching

### Problem & Solution

**Problem:**
- 35% of elderly (50+) experience chronic loneliness
- Limited access to social interaction due to mobility, health, or geographic isolation
- Existing chatbots use jargon, lack patience, and aren't tailored for elderly users

**Solution:**
- Patient, context-aware AI conversations available 24/7
- Simple voice-first interface requiring minimal technical skills
- Medication & wellness reminders to maintain health routines
- Cognitive games to slow mental decline
- Multilingual support respecting cultural preferences

### Key Statistics

| Metric | Value |
|--------|-------|
| **Supported Languages** | 2 (English, Cantonese/zh-HK) |
| **Backend Lines** | 2,359 lines (run.py with full schema, LLM, reminders) |
| **Backend Routes** | 21 endpoints (auth, chat, reminders, health, utilities) |
| **Frontend Templates** | 5 (login, register, chat, accessibility, hk_guide) |
| **Database Tables** | 4 (users, reminders, chat_history, preferences) |
| **Database Indexes** | 7 (optimized for user, reminders, chat queries) |
| **Speech Languages** | 2 (en-US, zh-HK) |
| **Mobile Platforms** | 2 (iOS 13+, Android 6+) |
| **Response Time** | 2–5 seconds (Zhipu LLM inference) |

---

## Technology Stack

### Backend Architecture

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Framework** | FastAPI | 0.115.12 | Async HTTP server, routing |
| **ASGI Server** | Uvicorn | 0.34.2 | Production-ready async server |
| **LLM Provider** | Zhipu AI | GLM-4 Flash | Conversational AI (bilingual) |
| **Database Driver** | psycopg2 | 2.9.10 | PostgreSQL connectivity |
| **Session Handler** | itsdangerous | 2.2.0 | Secure session signing |
| **HTTP Client** | httpx | 0.28.1 | Async API calls |
| **Template Engine** | Jinja2 | 3.1.6 | Server-side rendering |
| **Form Parser** | python-multipart | 0.0.20 | Multipart form handling |
| **WSGI Server** | Gunicorn | 23.0.0 | Production multi-worker |

**Python Version:** 3.12+

### Frontend Architecture

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Framework** | Bootstrap | 5.3.2 | Responsive grid & components |
| **DOM** | jQuery | 3.7.1 | Event handling, AJAX |
| **Icons** | Font Awesome | 6.4.0 | UI icons |
| **Calendar** | FullCalendar | 6.1.11 | Events & HK holidays |
| **Speech** | Web Speech API | native | Browser STT/TTS |
| **Styling** | CSS 3 | native | Glassmorphism, themes |
| **Mobile** | Capacitor | 6.2.1 | iOS/Android bridge |
| **Fonts** | Google Fonts | native | Inter + Noto Sans HK |

### Database Schema (PostgreSQL)

```sql
-- Users table (authentication & profile)
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  username TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_login TIMESTAMP,
  is_active BOOLEAN DEFAULT TRUE
);

-- Reminders table (medication, activity scheduling)
CREATE TABLE reminders (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  label TEXT NOT NULL,                    -- "吃藥", "運動", etc.
  reminder_time TEXT NOT NULL,            -- "09:00" format
  is_active BOOLEAN DEFAULT TRUE,
  repeat_type TEXT DEFAULT 'once',        -- 'once', 'daily', 'weekly'
  priority TEXT DEFAULT 'normal',         -- 'low', 'normal', 'high'
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chat history table (conversation logs)
CREATE TABLE chat_history (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  lang TEXT DEFAULT 'en',                 -- 'en' or 'zh-HK'
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  is_bot BOOLEAN NOT NULL,                -- TRUE if bot message
  message TEXT NOT NULL,
  is_deleted BOOLEAN DEFAULT FALSE,
  token_count INTEGER                     -- For LLM context tracking
);

-- User preferences table (language, theme, settings)
CREATE TABLE preferences (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  pref_key TEXT NOT NULL,                 -- 'language', 'theme', 'voice_enabled'
  pref_value TEXT NOT NULL,               -- 'en', 'zh-HK', 'dark', 'light', 'true'
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, pref_key)
);

-- Indexes (performance optimization)
CREATE INDEX idx_users_email_lower ON users ((LOWER(email)));
CREATE INDEX idx_reminders_user ON reminders(user_id, is_active);
CREATE INDEX idx_chat_user_time ON chat_history(user_id, timestamp);
CREATE INDEX idx_chat_deleted ON chat_history(user_id, is_deleted);
CREATE INDEX idx_pref_user ON preferences(user_id, pref_key);
CREATE INDEX idx_reminders_date ON reminders(user_id, created_at);
CREATE INDEX idx_chat_lang ON chat_history(user_id, lang);
```

**Database Provider:** PostgreSQL 12+ (Supabase / Neon / Self-hosted)

---

## API Endpoints

### Authentication Routes

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| GET | `/login` | Render login form | 200 |
| POST | `/login` | Authenticate user | 302 / 400 |
| GET | `/register` | Render registration form | 200 |
| POST | `/register` | Create user account | 302 / 400 |
| GET | `/logout` | Clear session | 302 |
| GET | `/forgot_password` | Password reset (placeholder) | 302 |

### Chat & Conversation

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| GET | `/` | Main chat UI (protected) | 200 / 302 |
| POST | `/get_response` | Send message, get LLM response | 200 |
| POST | `/transcribe` | Convert audio WAV to text | 200 |
| GET | `/get_chat_history` | Load message history | 200 |

### What Makes It Different

The project is intentionally built to behave more like a consistent companion than a generic chatbot. The difference is not only in the model choice, but in the way the conversation stack is constrained and presented.

- **Elderly-first persona design**: `run.py` does not rely on a default chatbot tone. It injects custom system prompts that require warmth, patience, simple wording, short replies, and culturally natural Cantonese or English.
- **Language-specific memory**: Conversation history is stored separately by both `user_id` and `lang`, so the assistant keeps the right tone, vocabulary, and context for each language instead of mixing them together.
- **Bounded context handling**: Only the most recent turns are sent to the LLM. This keeps replies coherent and personal without drifting into long, noisy, or overly formal responses.
- **Graceful degradation**: If the model API is unavailable, the app falls back to curated supportive responses rather than exposing technical failures. The user still gets a calm, conversational experience.
- **Companion-style delivery**: The frontend combines chat, voice input, text-to-speech, and gentle voice selection so the interaction feels more like a supportive conversation than a utility interface.

In practice, this means the assistant is tuned for emotional continuity, accessibility, and trust. It is designed to remember enough to feel familiar, but not so much that the conversation becomes cluttered or unstable.

### Reminders Management

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| GET | `/get_reminders` | List active reminders | 200 |
| POST | `/deactivate_reminder` | Mark reminder as inactive | 200 |

### Information Endpoints

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| GET | `/get_hk_holidays` | HK public holidays | 200 |
| GET | `/get_news` | Latest HK news | 200 |
| GET | `/get_hk_guide` | HK travel guide | 200 |

### Health & Diagnostics

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| GET | `/health` | Server health check | 200 |
| GET | `/health/db` | Database connectivity | 200 / 503 |

### Language & Accessibility

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| GET | `/set_language/{lang}` | Switch language (en/zh-HK) | 302 |
| GET | `/accessibility` | Large-text mode | 200 |

**Command Examples:**
- `"set reminder take medicine 09:00"` – Create reminder
- `"delete reminder take medicine"` – Soft-delete reminder
- `"play game"` – Start trivia quiz
- `"answer paris"` – Answer quiz question

---

## Features

| Feature | Status | Implementation |
|---------|--------|---|
| Conversational AI | ✅ | Zhipu GLM-4 LLM |
| Voice Input/Output | ✅ | Web Speech API |
| Smart Reminders | ✅ | PostgreSQL + async scheduler |
| Memory Games | ✅ | Trivia with score tracking |
| Calendar | ✅ | FullCalendar.js + HK holidays |
| News Feed | ✅ | NewsAPI + fallback |
| Dark Theme | ✅ | CSS variables + localStorage |
| Responsive Design | ✅ | Bootstrap 5 mobile-first |
| Accessibility | ✅ | WCAG AA, large buttons, ARIA |
| Bilingual UI | ✅ | English + Cantonese i18n |
| Mobile Apps | ✅ | Capacitor iOS/Android |
| Analytics | ✅ | GA4 + Vercel Insights |
| Push Notifications | 🟡 | Capacitor plugin ready |
| Multi-tenant | 🔴 | TODO |

---

## Quick Start

### Prerequisites

- **Python 3.12+** – `python --version`
- **Node.js 18+** – `node --version` (for mobile)
- **Git** – `git --version`
- **PostgreSQL 12+** (Supabase / Neon / Docker)

### Installation

```bash
# 1. Clone repository
git clone https://github.com/Brian-code-123/The-Listening-Tree.git
cd The-Listening-Tree

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Node dependencies (for mobile)
npm install
```

### Configuration

**Create `.env` file (copy from `.env.example`):**

```bash
# Zhipu AI API (required)
ZHIPU_API_KEY="sk-..."
ZHIPU_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
ZHIPU_MODEL="glm-4-flash"

# Database (required) — Use one:
# Option 1: Supabase
DATABASE_URL="postgresql://[user]:[password]@[host]:5432/[database]?sslmode=require"

# Option 2: Self-hosted PostgreSQL
DATABASE_URL="postgresql://user:password@localhost:5432/listening_tree"

# Security (required)
SECRET_KEY="<64-char-hex>"  # Generate: python -c "import secrets; print(secrets.token_hex(32))"

# Optional services
NEWS_API_KEY="<your-newsapi-key>"     # For news feed (fallback if missing)
PORT="5000"                            # Server port
ENVIRONMENT="development"              # or "production"
MAX_DB_CANDIDATES=20                   # Fallback DB candidates (multi-region)
PG_RETRY_INTERVAL_SEC=5                # PostgreSQL retry backoff
```

**Environment Validation:**
- 🔴 **DATABASE_URL is required** – App won't start without it
- 🟡 **NEWS_API_KEY is optional** – News endpoint disabled without it
- 🟢 **All other vars have safe defaults**

**Setup Methods:**

1. **Supabase (Recommended):**
   - Sign up: https://supabase.co
   - Create new project → Retrieve connection string → Add to `.env`
   - Auto-migration: Run `python run.py` → creates tables

2. **Docker PostgreSQL:**
   ```bash
   docker run -d -p 5432:5432 \
     -e POSTGRES_DB=listening_tree \
     -e POSTGRES_PASSWORD=secure_pwd \
     postgres:15
   # Then: DATABASE_URL="postgresql://postgres:secure_pwd@localhost:5432/listening_tree"
   ```

3. **Render / Railway / Railway:**
   - Free PostgreSQL provided → Copy connection string

### Running Locally

**Backend:**
```bash
# Option 1: Direct Python
python run.py
# Server: http://localhost:5000
# Logs: [DB] ✅ PostgreSQL initialized, [STT] ✅ Browser Web Speech API ready

# Option 2: Via npm (if available)
npm run dev

# Option 3: With Uvicorn directly
uvicorn run:app --reload --host 0.0.0.0 --port 5000
```

**Frontend:**
- Automatically served by FastAPI at `http://localhost:5000`
- Register test account: email: `test@example.com`, password: `test1234`
- Chat page auto-loads after login

**Health Check:**
```bash
curl http://localhost:5000/health
curl http://localhost:5000/health/db
```

**Logs to Monitor:**
- `[DB] ✅ PostgreSQL database initialized` — Schema created
- `[STT] ✅ Browser Web Speech API ready` — Voice input ready
- `[REMINDER] ⏰ Triggered: medication` — Reminder scheduler working

---

## Usage

### Text Chat

1. Type message in input box
2. Press Send or Enter
3. Bot responds in 2–5 seconds

### Voice Interaction

1. Click Microphone icon (🎤)
2. Speak clearly in English or Cantonese
3. Text appears automatically in input box
4. Press Send to get response

**Languages:** `en-US`, `zh-HK`

### Reminders

**Set (English):**
```
"set reminder take medicine 09:00"
"set reminder exercise 14:30"
```

**Set (Cantonese):**
```
"設置提醒 吃藥 09:00"
"設置提醒 每日散步 18:30"
```

**Delete (English):**
```
"delete reminder take medicine"
```

**Delete (Cantonese):**
```
"刪除提醒 吃藥"
```

**View:** Click Reminders panel (right sidebar)

**Time Format:** 24-hour format (HH:MM), e.g., `09:00`, `14:30`

### Games

**Start (English):**
```
"play game"
```

**Start (Cantonese):**
```
"玩遊戲"
```

**Answer (Flexible Matching):**
```
"answer paris"           # Exact match
"paris"                  # Auto-detected answer
"answer 巴黎"           # Cantonese answers accepted
"答 藍色"               # Cantonese format
"每個月"                 # Substring match: matches "每個月都有至少28日"
```

**Answer Recognition:**
- ✅ **Exact Match:** "paris" = "paris"
- ✅ **Substring Match:** "每個月" matches "每個月都有至少28日" (min 2 chars)
- ✅ **Case-Insensitive:** "PARIS" = "paris"
- ✅ **Cantonese:** Full support for zh-HK answers

**Exit Game:**
```
"exit game"  or  "退出遊戲"
```

### Calendar

- **View:** Click Calendar tab
- **See holidays:** Hong Kong public holidays highlighted in red
- **Click date:** View reminders for that day

### Language & Theme

- **Language:** Click EN or 繁中 (top right)
- **Theme:** Click Sun/Moon icon to toggle dark/light mode

---

## Project Structure

```
The-Listening-Tree/
├── run.py                    # FastAPI main app (2,359 lines, 21 routes, full schema)
├── translations.py           # Bilingual i18n (EN + zh-HK)
├── requirements.txt          # Python dependencies
├── package.json              # Node.js dependencies
├── Dockerfile                # Docker build
├── capacitor.config.ts       # Mobile app config
├── .env.example              # Environment template
│
├── templates/                # HTML templates (Jinja2)
│   ├── chat.html            # Main chat UI (326 lines)
│   ├── login.html           # Login form
│   ├── register.html        # Registration form
│   ├── accessibility.html   # Large-text mode
│   └── hk_guide.html        # HK travel guide
│
├── static/                  # Frontend assets
│   ├── style.css            # CSS3 (235 lines)
│   ├── components.js        # UI component builders
│   ├── Chatbot.png          # Bot avatar
│   ├── User.png             # User avatar
│   └── notification.mp3     # Reminder sound
│
├── www/                     # Web assets (Capacitor)
│   ├── index.html           # App entry point
│   ├── manifest.json        # PWA manifest
│   └── vendor/              # Local vendor libraries
│       ├── css/             # Bootstrap, FontAwesome
│       ├── js/              # jQuery, Bootstrap.js
│       └── webfonts/        # Font files
│
├── scripts/                 # Deployment scripts
│   ├── mobile-dev.sh        # iOS/Android live-reload
│   ├── migrate_sqlite_to_postgres.py
│   └── verify_supabase_postgres.py
│
├── tests/                   # Backend tests (pytest)
│   ├── test_basic.py
│   ├── test_core_flows.py
│   └── test_session_persistence_unit.py
│
├── ios/                     # Native iOS (Xcode)
├── android/                 # Native Android (Android Studio)
└── utils/supabase/          # Supabase client
```

### Key Modules

| File | Purpose |
|------|---------|
| `run.py` | FastAPI routes, LLM calls, DB queries, scheduler |
| `chat.html` | Main UI, Web Speech API, AJAX, FullCalendar |
| `style.css` | Glassmorphism design, responsive layout |
| `translations.py` | i18n strings (EN + zh-HK, 400+ keys) |
| `package.json` | Scripts: dev, test, mobile, deploy |

---

## Development

### Code Standards

**Python (PEP 8):**
- 4-space indentation
- Type hints for functions
- Docstrings for public functions
- Use async/await for I/O

**Frontend:**
- Semantic HTML (nav, section, main, button)
- Mobile-first responsive design
- WCAG AA accessibility (focus, contrast, ARIA labels)

### Testing

```bash
# Run backend tests
npm run test:backend
# or
pytest tests/ -v

# Manual checklist
# [ ] Register & login
# [ ] Chat & get response
# [ ] Voice input
# [ ] Set/delete reminder
# [ ] Play game
# [ ] Calendar & holidays
# [ ] Language toggle
# [ ] Dark/light theme
# [ ] Mobile responsive
# [ ] Accessibility (Tab navigation, screen reader)
```

### Git Workflow

**Branch naming:**
```
feature/xyz      # New feature
bugfix/xyz       # Bug fix
refactor/xyz     # Code refactoring
docs/xyz         # Documentation
ci/xyz           # CI/CD
```

**Commit messages:**
```
feat:  Add emotion detection
fix:   Correct time parsing
refactor: Extract LLM logic
docs:  Update README
test:  Add unit tests
style: Format code
ci:    Update workflows
```

**Pull Request:**
1. Create branch: `git checkout -b feature/xyz`
2. Code & test locally
3. Commit: `git commit -m "feat: description"`
4. Push: `git push origin feature/xyz`
5. Open PR describing changes
6. Request review
7. Merge after approval

---

## Deployment

### Web (Vercel / Render)

**Vercel (Recommended):**
```bash
# 1. Push to GitHub
git push origin main

# 2. Deploy
npm install -g vercel
vercel --prod

# 3. Set environment variables in Vercel Dashboard
# ZHIPU_API_KEY, DATABASE_URL, SECRET_KEY

# 4. Verify
curl https://<project>.vercel.app/health/db
```

**Render (Free Tier):**
1. Go to render.com → New Web Service
2. Connect GitHub repo, select `main` branch
3. Build: Auto-detect Dockerfile
4. Start: `gunicorn -w 2 -k uvicorn.workers.UvicornWorker run:app`
5. Add env vars
6. Deploy

### Mobile (iOS / Android)

**iOS:**
```bash
npm run cap:sync
npm run cap:open:ios
# In Xcode: Set Team ID → Product → Run/Archive
```

**Android:**
```bash
npm run cap:sync
npm run cap:open:android
# In Android Studio: Build → Generate Signed APK/Bundle
```

### Docker Self-Hosted

```bash
# Build
docker build -t listening-tree:latest .

# Run
docker run -d \
  --name listening-tree \
  -p 5000:5000 \
  -e ZHIPU_API_KEY="sk-..." \
  -e DATABASE_URL="postgresql://..." \
  -e SECRET_KEY="<hex>" \
  listening-tree:latest

# Check logs
docker logs listening-tree
```

**Docker Compose:**
```bash
docker-compose up -d
```

---

## Troubleshooting & FAQ

**Q: How do I add a new command?**
A: Edit `run.py`, add condition in `/get_response` route, return response string.

**Q: Can I use OpenAI instead of Zhipu?**
A: Replace `zhipu_api_call()` function in `run.py` with OpenAI SDK.

**Q: Why does voice fail?**
A: Check browser microphone permissions, speak clearly, ensure quiet environment.

**Q: Can this run on Raspberry Pi?**
A: Yes with Docker. RPi 4 (2GB+) supported, but LLM inference will be slow.

**Q: How do I encrypt conversation data?**
A: Use PostgreSQL `pgcrypto` extension, encrypt before INSERT, decrypt on SELECT.

**Q: How do I change UI colors?**
A: Edit `static/style.css` CSS variables (--primary-color, --bg-light, etc.).

**Q: How do I make this multi-tenant?**
A: Add `organization_id` to all tables, filter queries by org_id.

---


## License

**Academic Use Only** – Educational and research use permitted. See [LICENSE](LICENSE) for full terms.

**Commercial Use:** Contact creator for licensing.

---

**Last Updated:** May 2026 | **Status:** Stable, Production-Ready | **Maintainer:** @Brian-code-123

**Recent Updates (May 2026):**
- ✨ Intelligent quiz answer matching: substring validation for flexible answers
- 🐛 Fixed: zh-* language code support (zh, zh-CN, zh-HK)
- 📊 Database: Full PostgreSQL/Supabase migration complete
- 🔐 Security: RLS policies recommended, all secrets env-managed
- 📈 Schema: 7 indexes for performance optimization
