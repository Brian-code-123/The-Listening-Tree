# Requirements

> This document formalizes the scope of an already-shipped iterative build,
> written retroactively for FYP documentation and supervisor review. It is
> not a claim that development followed a waterfall spec-first process — it
> didn't. It exists so the project has a single reference for "what is this
> for and who is it for" that isn't scattered across commit messages.

## Target user

An elderly Hong Kong resident (roughly 60+) who:

- Speaks Cantonese as a first language, with variable comfort in English.
- May have limited experience with smartphone apps beyond messaging.
- Experiences some degree of social isolation — lives alone, or has reduced
  regular in-person contact with family/friends.
- Manages one or more daily routines (medication, exercise, hydration) that
  benefit from reminders.
- May have mild vision, hearing, or fine-motor limitations that make small
  text, low contrast, and precise tapping harder than for a younger user.

A secondary user, implicit in the "not just elderly people" framing used for
this project's own usability testing, is anyone acting as that person's
family member or informal carer, who may set up the account or check in on
reminders on their behalf.

## Core user stories

1. As an elderly user who feels isolated, I want to have a warm, patient
   conversation with an AI companion in my own language, so that I have
   someone to "talk to" between calls from family.
2. As a Cantonese-first speaker, I want to switch between Cantonese and
   English at any point without losing my conversation, so that I can use
   whichever language I'm more comfortable with in the moment.
3. As someone managing daily medication/exercise/hydration, I want to set a
   spoken or typed reminder ("remind me to take my blood pressure pills at
   8am") and be alerted when it's due, so that I don't have to rely on
   memory alone.
4. As a user with limited typing comfort, I want to speak to the app instead
   of typing, so that voice is a first-class input method, not an
   afterthought.
5. As a returning user, I want to find and continue an earlier conversation
   instead of starting over every time, so that context (and the
   relationship with the companion) isn't lost session to session.
6. As a user with many past conversations, I want to pin the important ones
   and tag them by topic (family, health, daily life, etc.), so that the
   list stays navigable as it grows instead of becoming an undifferentiated
   scroll.
7. As a user with low vision or reduced fine motor control, I want large
   text, high contrast, and large touch targets throughout, so that the app
   doesn't require precision or straining to read.
8. As a Hong Kong resident, I want quick access to local public holidays and
   news relevant to daily life, so that the app is useful beyond just chat.

## Non-functional requirements

- **Accessibility**: UI aims for WCAG AA-aligned contrast and typography;
  large tap targets; minimal navigation depth; no reliance on hover-only or
  gesture-only interactions.
- **Bilingual parity**: every user-facing string and AI response path must
  work equivalently in English and Cantonese (zh-HK) — not English-first
  with Cantonese as an incomplete afterthought.
- **Response latency**: conversational replies should typically land within
  2-5 seconds (LLM round-trip); voice transcription and reminder checks are
  allowed more slack (up to ~60s for reminder delivery) since they aren't in
  the user's direct interaction loop.
- **Session security**: authenticated sessions must survive app restarts on
  the client side (remember-me) without weakening server-side session
  secret handling; failed login attempts must be rate-limited to slow
  credential-guessing without permanently locking out a legitimate user.
- **Privacy**: voice processing prefers on-device/browser-native APIs over
  server-side transcription where the browser supports it; only falls back
  to a server call when necessary.
- **Availability on constrained connections**: since the primary user base
  may be on older devices or slower home connections, the app should
  degrade gracefully (e.g. voice input falling back to server-side
  transcription) rather than failing hard.

## Out of scope (explicitly, for this project's current phase)

- Multi-tenant/organizational accounts (e.g. a care home managing many
  residents from one dashboard) — single personal account per user only.
- Real-time human-to-human messaging between users — this is a
  user-to-AI-companion product, not a social network.
- Medical advice or diagnosis — reminders and conversation are wellness
  support, not a substitute for professional healthcare guidance.

## Frontend Modernization Roadmap

See [`FRONTEND_ROADMAP.md`](./FRONTEND_ROADMAP.md) for the staged plan to
move the web frontend from server-rendered Jinja2 + jQuery to a Next.js
SPA/hybrid app, once the backend modularization (below) gives it a stable
API surface to build against. Not scheduled for the current build phase.
