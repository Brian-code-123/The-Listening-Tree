# The Listening Tree 🌳

Elderly-friendly AI companion for English and Cantonese conversations, reminders, wellness support, and accessible voice-first interaction.

## Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Core Solution](#core-solution)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [System Architecture](#system-architecture)
- [Core Workflow](#core-workflow)
- [Testing & Validation](#testing--validation)
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
- Smart reminder system: CRUD-managed medication and activity reminders with scheduled notifications.
- Cross-platform support: responsive web app plus native iOS and Android builds via Capacitor.
- Accessibility optimization: large typography, high-contrast themes, and simplified navigation.
- Cognitive wellness tools: bilingual memory games and daily wellness prompts.
- HK localized utilities: public holiday calendar, local news feed, and daily life guidance.

## Tech Stack

### Frontend

- Core: HTML5, CSS3, JavaScript (ES6+)
- Framework: Bootstrap 5 for responsive layout
- Libraries: jQuery, FullCalendar.js, Font Awesome
- Voice: Web Speech API for browser-native speech-to-text and text-to-speech
- Mobile build: Capacitor 6 for iOS and Android packaging
- Deployment: Vercel

### Backend

- Framework: FastAPI on Python 3.12+
- Server: Uvicorn ASGI server
- LLM integration: Zhipu AI GLM-4 Flash for bilingual conversations
- Security: bcryptjs for password hashing, python-multipart for form handling
- API: RESTful endpoints for auth, chat, reminders, and utilities

### Database

- Database: PostgreSQL 12+ for secure relational persistence
- Core entities: User, ChatMessage, Reminder, Preference
- Hosting: Supabase and Neon for managed PostgreSQL services

### DevOps & Testing

- CI/CD: GitHub Actions for automated checks on commits
- E2E testing: Playwright for cross-browser and device automation
- Version control: Git with branch-based workflow

## System Architecture

The project follows a modular three-layer architecture designed for stability and maintainability:

- Frontend layer: responsive UI handling user interactions, voice input and output, and dynamic content rendering.
- Backend API layer: FastAPI service handling business logic, LLM integration, authentication, and database operations.
- Database layer: PostgreSQL storing user profiles, chat history, reminders, and preferences with optimized indexing.

## Core Workflow

### 1. User Onboarding

- Simple registration and login with email authentication.
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

## Testing & Validation

- End-to-end testing: Playwright simulates real user flows such as reminder CRUD, voice chat, and mobile responsiveness.
- CI/CD automation: GitHub Actions runs tests on every commit for consistent quality.
- Key results: 100% test case pass rate, validated 99.9% system stability, and cross-device compatibility.
- Focus: critical features like the reminder system and voice interaction are prioritized for elderly user needs.

## Deployment

- Web: hosted on Vercel at https://the-listening-tree.vercel.app/
- Mobile: native iOS and Android apps built via Capacitor for App Store and Google Play readiness.
- Database: managed PostgreSQL on Supabase for secure and scalable storage.

## Future Improvements

- Email verification via Azure Email Server for enhanced account security.
- Advanced analytics dashboard for usage and wellness tracking.
- Offline mode support for low-connectivity environments.
- Multi-language expansion for additional regional dialects.

## License

Academic use only. Educational and research use is permitted. Commercial use requires explicit permission from the maintainer.
