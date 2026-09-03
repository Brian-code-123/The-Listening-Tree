# The Listening Tree 🌳

Elderly-friendly AI companion for English and Cantonese conversations, reminders, wellness support, and accessible voice-first interaction.

## Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Core Solution](#core-solution)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [System Architecture](#system-architecture)
- [Quick Start](#quick-start)
- [Core Workflow](#core-workflow)
- [Testing & Evaluation Methodology](#testing--evaluation-methodology)
- [Security & Privacy](#security--privacy)
- [Deployment](#deployment)
- [Future Improvements](#future-improvements)
- [License](#license)

## Overview

The Listening Tree is a bilingual AI-powered companion chatbot designed to reduce loneliness, enhance daily wellness, and improve digital accessibility for elderly users. It uses a voice-first, elderly-centric design to help older adults navigate modern technology with less friction.

## Problem Statement

Elderly populations face severe digital and social barriers:

- Loneliness crisis: around 25% of older adults experience social isolation, which is linked to accelerated cognitive decline and dementia risk.
- Tech accessibility gaps: complex interfaces, tiny text, and confusing navigation make common apps difficult to use.
- Health management burden: missed medication schedules can lead to health risks.
- Limited social interaction: mobility or geographic restrictions can reduce daily social engagement and harm mental health.

## Core Solution

The Listening Tree delivers a compassionate, intuitive AI companion tailored for elderly users with four main goals:

- Simplicity and personalization: easy, customizable daily reminders for medication, exercise, and hydration.
- Voice-first interaction: hands-free operation via Cantonese and English voice commands.
- Elderly-centric design: WCAG AA-aligned UI with large buttons, high contrast, and minimal clutter.
- Security and reliability: rigorously tested system with strong data protection for user privacy.

## Key Features

- Bilingual AI chatbot: warm, patient conversations powered by Zhipu AI GLM-4 LLM in English and Cantonese.
- Voice interaction: Web Speech API for real-time speech recognition and synthesis.
- Smart reminder system: CRUD-managed medication and activity reminders. In-browser polling drives an in-app alarm (sound + on-screen alert); on the native mobile build, reminders are also scheduled as local OS notifications so they still fire while the app is backgrounded or closed.
- Conversation history: dedicated history page for browsing, pinning, tagging, and renaming past conversations, separate from the always-current active chat.
- Cross-platform support: responsive web app plus native iOS and Android builds via Capacitor.
- Accessibility optimization: large typography, high-contrast themes, and simplified navigation.
- Cognitive wellness tools: bilingual memory games and daily wellness prompts.
- HK localized utilities: public holiday calendar, local news feed, and daily life guidance.

## Tech Stack

### Frontend

- Core: HTML5, CSS3, JavaScript (ES6+)
- Framework: Bootstrap 5 for responsive layout
- Libraries: jQuery, FullCalendar.js, Font Awesome
- Voice: Web Speech API for browser-native speech-to-text and text-to-speech, with a server-side `/transcribe` fallback (Hugging Face Whisper, then legacy Google Web Speech via `SpeechRecognition`) for browsers without Web Speech API support
- Mobile build: Capacitor 6 for iOS and Android packaging, with `@capacitor/local-notifications` for background reminder alarms
- Deployment: Vercel

### Backend

- Framework: FastAPI on Python 3.12+
- Server: Uvicorn ASGI server
- LLM integration: Zhipu AI GLM-4 Flash for bilingual conversations
- Security: PBKDF2-HMAC-SHA256 (per-user salt) for password hashing, python-multipart for form handling
- Auth: email/password with account lockout after repeated failed attempts, plus optional Google Sign-In (OAuth 2.0 via Authlib) — auto-links to an existing password account by email if one already exists
- API: RESTful endpoints for auth, chat, reminders, and utilities

### Database

- Database: PostgreSQL for secure relational persistence
- Core tables: `users`, `chat_history`, `reminders`, `preferences`, `email_verifications`, `conversations`
- Hosting: Supabase (managed PostgreSQL with connection pooler)
- Schema migrations: Alembic (`alembic/versions/`) — run `alembic upgrade
  head` after pulling a change that touches the schema; `python run.py`
  also bootstraps a brand-new database on its own for local dev
  convenience, but ongoing schema changes are written as Alembic revisions,
  not edits to that bootstrap code

### DevOps & Testing

- CI/CD: GitHub Actions for automated checks on commits
- E2E testing: Playwright for cross-browser and device automation
- Version control: Git with branch-based workflow

## System Architecture

The project follows a modular three-layer architecture designed for stability and maintainability:

- Frontend layer: Jinja2-templated pages (`templates/`) for chat, login, register, accessibility, and HK guide, plus a standalone Capacitor shell (`www/`) for the mobile build — handling user interactions, voice input and output, and dynamic content rendering.
- Backend API layer: FastAPI service handling business logic, LLM integration, authentication, and database operations.
- Database layer: PostgreSQL storing user profiles, chat history, reminders, and preferences with optimized indexing.

## Quick Start

The frontend is currently split across two stacks during an in-progress
migration: `/history`, `/register`, `/login`, `/profile`, `/accessibility`,
and `/hk_guide` are served by the Next.js app in `web-next/`; everything
else — including `/` (the main chat page), until `/chat` ships — is still
the FastAPI/Jinja app in `templates/`. Both need to run for local dev.

### Backend

```bash
pip install -r requirements.txt
python run.py            # http://localhost:5000
PORT=5001 python run.py  # or on a different port
```

### `web-next/`

```bash
cd web-next
npm install
npm run dev               # http://localhost:3001
```

Locally the two run as separate origins, so `web-next/.env.local`
(gitignored) needs `NEXT_PUBLIC_API_BASE` pointed at wherever the
backend is running, e.g.:

```
NEXT_PUBLIC_API_BASE=http://localhost:5000
```

In production both are deployed together behind one origin via
`vercel.json`'s `services`/`rewrites` config, so this env var is unset
there (same-origin relative fetches).

## Core Workflow

### 1. User Onboarding

- Registration with email verification code (sent via Azure Communication Services) and login with email authentication, or sign in directly with Google.
- Bilingual setup in English or Cantonese plus theme selection for standard or high-contrast mode.
- AI voice greeting for a friendly first experience.

### 2. Reminder Management

- Voice command to create reminders, for example: "Set daily 8 AM BP meds reminder".
- AI confirms details in large text.
- Edit or delete reminders through voice or simple UI gestures.

### 3. Bilingual Interaction

- Voice queries in Cantonese or English for weather, time, and daily tips.
- AI responds in the user’s language with clear, slow speech.
- Seamless language switching with one click.

## Testing & Evaluation Methodology

### Automated testing

- Unit testing: Vitest for JavaScript utility functions.
- Integration testing: pytest against an ephemeral PostgreSQL container, covering registration with email verification, login, reminder CRUD, AI chat, cognitive game flow, and voice transcription.
- End-to-end testing: Playwright simulates real user flows such as reminder CRUD, voice chat, and mobile responsiveness.
- CI/CD automation: GitHub Actions runs unit and integration tests on every push/PR to `main`/`develop`; Playwright E2E tests are run locally/manually and are not yet wired into CI.

### Known evaluation gaps

Automated test pass rate reflects functional correctness, not usability. The project does not yet include:

- A formal System Usability Scale (SUS) study with elderly test participants.
- Measured response latency / throughput benchmarks under load.
- A structured user feedback or focus-group study.

These are tracked as future work (see [Future Improvements](#future-improvements)).

## Security & Privacy

- Password storage: PBKDF2-HMAC-SHA256 with a unique per-user salt (390,000 iterations), never plaintext or reversibly encrypted.
- Session integrity: session signing key is read from `SECRET_KEY`/`SESSION_SECRET`; in production, startup fails fast if no persistent secret is configured, preventing silent use of a throwaway key that would invalidate all sessions on restart.
- Verification code abuse prevention: `/send_verification_code` enforces a server-side cooldown per email address, rejecting rapid repeat requests with HTTP 429.
- Database access: connections use Supabase's managed connection pooler rather than raw per-request connections; credentials are read from environment variables, never hardcoded.
- SQL injection prevention: all queries use parameterized placeholders via the `db_execute` helper.

### Known gaps

- Encryption-at-rest relies on Supabase's underlying infrastructure and is not independently documented or verified at the application level.
- No formal written threat model.
- No documented data retention / deletion policy for user accounts and chat history.

## Deployment

- Web: hosted on Vercel at https://the-listening-tree.vercel.app/
- Mobile: native iOS and Android apps built via Capacitor for App Store and Google Play readiness.
- Database: managed PostgreSQL on Supabase for secure and scalable storage.

## Future Improvements

- Formal usability evaluation with an elderly test group, using the System Usability Scale (SUS) methodology.
- Documented threat model and data retention / deletion policy.
- Advanced analytics dashboard for usage and wellness tracking.
- Offline mode support for low-connectivity environments.
- Multi-language expansion for additional regional dialects.

## License

Academic use only. Educational and research use is permitted. Commercial use requires explicit permission from the maintainer.
