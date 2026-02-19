# The Listening Tree 🌳

> **Compassionate AI Companion for Elderly Wellness**
> Bilingual chatbot with glassmorphism UI, voice interaction, and intelligent reminders

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI 0.115](https://img.shields.io/badge/fastapi-0.115.12-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Uvicorn 0.34](https://img.shields.io/badge/uvicorn-0.34.2-4051B5)](https://www.uvicorn.org)
[![Gunicorn 23](https://img.shields.io/badge/gunicorn-23.0.0-499848?logo=gunicorn&logoColor=white)](https://gunicorn.org)
[![License](https://img.shields.io/badge/license-Academic-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-production-brightgreen)](#deployment)

---

## Overview

The Listening Tree is a **bilingual AI companion chatbot** (English + Traditional Chinese / Cantonese) designed to reduce loneliness in elderly populations. It provides warm, patient conversation, medication reminders, cognitive games, local news, and a Hong Kong public holidays calendar — all wrapped in an accessible glassmorphism interface.

**Core technology:** FastAPI backend → Kimi / Moonshot AI (LLM) → SQLite persistence → Bootstrap 5 + FullCalendar.js frontend.

---

## Features

| Feature | Description |
|---------|-------------|
| **AI Chat** | Kimi / Moonshot API (`moonshot-v1-8k`) with 8K context window and warm conversational tone |
| **Voice I/O** | Web Speech API for both English and Cantonese (browser-native, zero server deps); Vosk offline fallback for English |
| **Smart Calendar** | FullCalendar.js 6.1 with HK public holidays (2025–2027), voice-readable dates |
| **Reminders** | SQLite-backed reminders with background checker, browser notifications, alarm sound |
| **News Feed** | NewsAPI.org integration with 30-min cache; hardcoded HK news fallback |
| **Memory Games** | Bilingual trivia quizzes for cognitive engagement |
| **Glassmorphism UI** | Apple Liquid Glass design (`backdrop-filter: blur(16px)`); dark / light modes |
| **Accessibility** | WCAG AA (contrast ≥ 4.5:1), 48px touch targets, keyboard navigation, dedicated a11y page |
| **Bilingual** | Full EN + zh-HK with live language switching; per-language chat history |
| **Responsive** | 3-column desktop → stacked mobile layout with sidebar toggle |

---

## Quick Start

### Prerequisites

- **Python 3.12+** (or Docker)
- A free [Moonshot AI API key](https://platform.moonshot.cn) (100K tokens/month included)
- Modern browser with Web Speech API (Chrome, Edge, or Safari 14.1+)

### Local Development

```bash
# Clone
git clone https://github.com/yourusername/The-Listening-Tree.git
cd The-Listening-Tree

# Virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt          # Production packages
# pip install -r requirements-local.txt  # + Vosk offline STT (optional)

# Set environment variables (or create .env)
export KIMI_API_KEY="sk-your-moonshot-key"
export NEWS_API_KEY="your-newsapi-key"       # Optional

# Run
python run.py
```

Open **http://localhost:5000** in your browser.

### Docker

```bash
docker build -t the-listening-tree .
docker run -p 5000:5000 -e KIMI_API_KEY=sk-... the-listening-tree
```

### Render

Push to GitHub, then connect to [Render](https://render.com) as a Web Service. The included `render.yaml` auto-configures Gunicorn with `gunicorn==23.0.0`.

---

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                  Client (Browser)                      │
│  Bootstrap 5.3 · FullCalendar 6.1 · Font Awesome 6.4  │
│  Web Speech API (STT/TTS, EN + zh-HK)                 │
└────────────────┬───────────────────────────────────────┘
                 │  AJAX / JSON
┌────────────────┴───────────────────────────────────────┐
│               FastAPI 0.115.12 (Python)                │
│                                                        │
│  POST /get_response   → command parse OR Kimi LLM      │
│  POST /upload_file    → Kimi vision (image) / text     │
│  POST /transcribe     → Vosk offline STT (EN only)     │
│  GET  /get_reminders  → today's active reminders       │
│  GET  /get_hk_holidays→ static holiday dataset → JSON  │
│  GET  /get_news       → NewsAPI + in-memory cache      │
│  GET  /get_chat_history→ per-user, per-language msgs   │
│  POST /login /register→ session-based auth (SQLite)    │
└────────┬──────────┬──────────┬─────────────────────────┘
         │          │          │
      SQLite     Kimi API   NewsAPI.org
    reminders.db (Moonshot)  (optional)
```

---

## Technology Stack

| Layer | Package | Version | Purpose |
|-------|---------|---------|---------|
| **Framework** | FastAPI | 0.115.12 | Async ASGI web framework |
| **Server** | Uvicorn | 0.34.2 | Production ASGI server |
| **Production** | Gunicorn | 23.0.0 | Process manager (Render / Docker) |
| **AI / LLM** | Kimi (Moonshot) | v1-8k | Chat + image analysis + web search |
| **Database** | SQLite3 | built-in | Users, reminders, chat history, preferences |
| **Templates** | Jinja2 | 3.1.6 | Server-side HTML rendering |
| **HTTP** | httpx | 0.28.1 | Async HTTP client (AI + News API calls) |
| **Auth** | itsdangerous | 2.2.0 | Session signing |
| **Validation** | email-validator | 2.2.0 | Email format checking |
| **Multipart** | python-multipart | 0.0.20 | File upload handling |
| **JWT** | python-jose | 3.4.0 | Token utilities |
| **Voice** | Vosk | 0.3.45 | English STT — local dev only |
| **Frontend** | Bootstrap | 5.3.2 | Responsive layout |
| **Calendar** | FullCalendar.js | 6.1.11 | Interactive month calendar |
| **Icons** | Font Awesome | 6.4.0 | UI iconography |
| **DOM** | jQuery | 3.7.1 | DOM manipulation + AJAX |

---

## Project Structure

```
The-Listening-Tree/
├── run.py                  # FastAPI app — routes, AI, DB, reminders, holidays, news
├── translations.py         # i18n strings (EN + zh-HK, 200+ keys each)
├── templates/
│   ├── chat.html           # Main 3-column glassmorphism interface
│   ├── login.html          # Auth — login form
│   ├── register.html       # Auth — registration form
│   └── accessibility.html  # WCAG AAA large-text mode
├── static/
│   └── style.css           # Glassmorphism theme (light/dark, ~800 lines)
├── api/
│   └── index.py            # Vercel serverless entry point
├── voice_models/
│   └── vosk-model-small-en-us-0.15/  # Offline English STT (~100 MB)
├── requirements.txt        # Production dependencies
├── requirements-local.txt  # Dev dependencies (+ Vosk)
├── Dockerfile              # Single-stage python:3.12-slim
├── render.yaml             # Render PaaS deploy config
├── runtime.txt             # Python 3.12
├── vercel.json             # Vercel routing config
└── README.md
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `KIMI_API_KEY` | Yes | — | Moonshot AI API key |
| `KIMI_BASE_URL` | No | `https://api.moonshot.cn/v1` | AI API base URL |
| `KIMI_MODEL` | No | `moonshot-v1-8k` | LLM model name |
| `NEWS_API_KEY` | No | — | NewsAPI.org key (falls back to hardcoded articles) |
| `DATABASE_URL` | No | `./reminders.db` | SQLite path (`/tmp/...` on Vercel) |
| `PORT` | No | `5000` | Server port |
| `VERCEL` | No | — | Set automatically; disables background threads |

### Database

Four tables: **users**, **reminders**, **chat_history**, **preferences** — all with indexes for fast per-user queries. Auto-created by `init_db()` on first run.

---

## Voice Architecture

```
  ┌─ Web Speech API ──────────────────────────────┐
  │  Primary path for BOTH English and Cantonese   │
  │  → SpeechRecognition (lang: en-US / zh-HK)    │
  │  → interim results shown live in text field    │
  │  → final transcript auto-submits to chat       │
  └────────────────────────────────────────────────┘
           │ fallback (browser lacks Web Speech API)
  ┌─ Vosk Server-Side STT ────────────────────────┐
  │  English only · 16 kHz mono WAV via /transcribe│
  │  Offline model (~100 MB) · No cloud dependency │
  └────────────────────────────────────────────────┘

UX flow:
  • Tap mic → pulse animation + "Listening..." placeholder
  • Speak → live interim text appears in input field
  • Stop speaking → auto-submit (same pipeline as typing)
  • Error → friendly toast notification (not alert())
```

---

## Development

```bash
# Verify imports
python -c "from run import app; print('OK')"

# Run with auto-reload
uvicorn run:app --reload --port 5000
```

### Commit Convention

```
feat:     new feature
fix:      bug fix
refactor: code restructure (no feature change)
docs:     documentation only
style:    formatting / whitespace
perf:     performance improvement
```

---

## Contributing

1. Fork & clone
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Add translations for both EN and zh-HK in `translations.py`
4. Test locally with `python run.py`
5. Commit with conventional prefix and open a PR

### Ideas

- Additional language packs (Mandarin, Vietnamese)
- More memory games (jigsaw, music recognition)
- Health tracking integration (Apple Health / Google Fit)
- Recurring reminders with snooze
- Family group chat

---

## License

**Academic License** — Educational & Research Use.

For commercial use or third-party integration, please contact the developers.

---

## Credits

- **Moonshot AI** — Kimi LLM API
- **FullCalendar** — Calendar widget
- **Bootstrap** — Responsive framework
- **Vosk** — Offline STT engine
- **Font Awesome** — Icon library

---

**Built with ❤️ for elderly wellness · FYP 2026 · Python + FastAPI**
