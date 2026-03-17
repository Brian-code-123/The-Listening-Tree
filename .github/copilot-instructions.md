# AI Coding Agent Instructions for Elderly Companion Chatbot

## Project Overview
This is a FastAPI-based chatbot application designed to reduce loneliness in elderly populations through:
- **Natural language conversations** using Microsoft DialoGPT-Medium (transformer-based model)
- **Voice interaction** via Vosk offline speech recognition (no cloud dependency)
- **Memory games** with trivia/word-recall for cognitive engagement
- **Personalized reminders** for medications, exercise, social activities
- **Elderly-friendly UI** with large buttons, clear text, voice-first interaction

**Key Architecture**: Python FastAPI backend + SQLite persistence + client-side JavaScript for audio handling.

## Critical Developer Workflows

### Local Development
```bash
pip install -r requirements.txt          # Install Python dependencies
# Start the FastAPI app (uses Uvicorn ASGI server). Example:
#   uvicorn run:app --reload --host 0.0.0.0 --port 5000
python run.py                            # Start FastAPI server (http://localhost:5000)
```

### Containerized Deployment
```bash
docker build -t elderly-companion-chatbot .
docker run -p 5000:5000 -v elderly_data:/app elderly-companion-chatbot
```
The Dockerfile uses multi-stage builds: builder stage downloads 100MB+ Vosk models, runtime stage keeps image lean.

### Database Management
- SQLite file: `reminders.db` (created automatically on first run via `init_db()`)
- Tables: `users` (email/password), `reminders`, `chat_history`, `preferences`
- Each user identified by email stored in a server-side session (`request.session['user_id']`)

## Architecture Patterns

### 1. **Model Loading at Startup**
[run.py](run.py#L25-L32) loads DialoGPT and Vosk models globally at app startup. These are memory-intensive (DialoGPT-Medium ~2GB when loaded):
- `tokenizer` and `model` are global singletons
- `vosk_model` loads from `voice_models/vosk-model-small-en-us-0.15`
- Use `MAX_HISTORY_TOKENS = 1024` to prevent conversation context from growing unbounded

### 2. **Per-User Session State**
Two in-memory dictionaries track user context across requests:
```python
user_chat_histories[user_id]  # Stores token IDs (compressed conversation context)
user_game_states[user_id]     # Tracks quiz progress, current question index
```
These are NOT persisted to database—lost on server restart.

### 3. **Command-Based Bot Logic**
[run.py](run.py#L166-L210) routes special commands (case-insensitive, whitespace-trimmed):
- `"set reminder [activity] [HH:MM]"` → Insert into reminders table, validate time format
- `"delete reminder [activity]"` → Mark as inactive in database
- `"play game"` → Initialize quiz, return first question
- `"answer [response]"` → Check against questions list (case-insensitive partial match)
- Default fallback → Send user input to DialoGPT for response

### 4. **Voice Pipeline (Client-Side)**
[chat.html](templates/chat.html) uses Web Audio API + JavaScript to:
1. Capture audio via microphone → browser stores as WAV blob
2. POST audio to `/transcribe` endpoint (multipart/form-data)
3. Vosk models run server-side, return transcribed text
4. JavaScript appends transcribed text to chat input, auto-sends

### 5. **Background Reminder Thread**
[run.py](run.py#L85-L99) spawns daemon thread checking reminders every 60 seconds. Logs "REMINDER TRIGGERED" server-side; actual notification handled by client-side JavaScript (browser doesn't have direct access to system notifications due to security).

## Project-Specific Conventions

### Naming & Casing
- Table names: lowercase with underscores (`chat_history`, `reminders`)
- User ID: email address (lowercase), stored in `session['user_id']`
- Chinese comments found in code (authentication section) indicate multilingual developer team

### State Management Philosophy
- **Transient state** (chat context, game progress) → in-memory Python dictionaries
- **Persistent state** (accounts, preferences, message logs) → SQLite
- **Client secrets** → server-side session with `secrets.token_hex(16)` generated key (NOT hardcoded)

### Error Handling Patterns
- Register/login: `sqlite3.IntegrityError` catches duplicate emails; return error to template
- Reminder parsing: try/except around time validation; return user-friendly message on format error
- Voice transcription: partial matches on answers (e.g., "paris" matches capital of France response)

## Key Integration Points

### Dependencies & Their Role
| Package | Purpose | Notes |
|---------|---------|-------|
| `fastapi` | Web framework, routing, session management (Starlette sessions) | Secret key generated per session |
| `transformers` + `torch` | DialoGPT model inference | Requires CUDA for GPU acceleration; CPU-only on ARM |
| `vosk` | Offline speech recognition | Lightweight; 100MB model download |
| `sqlite3` | Database (builtin) | Single `.db` file; concurrent write locks possible |
| `pydub` | Audio format conversion | Used for voice file processing |

### Routes & Data Flow
```
User Login/Register → POST /register, /login → SQLite users table → Session set
Chat Send → POST /get_response → Command parsing OR DialoGPT inference → SQLite chat_history log
Voice Input → POST /transcribe (audio) → Vosk STT → /get_response with transcribed text
Reminder Set → Command parser → INSERT reminders table → Background thread checks every 60s
```

### HTML Template Structure
- [chat.html](templates/chat.html): Main chat interface, voice recording UI, JavaScript event handlers
- [login.html](templates/login.html): Form POST to `/login`, email/password fields
- [register.html](templates/register.html): Form POST to `/register`, email validation (regex check)
- All styled with Bootstrap 5 + custom CSS ([style.css](static/style.css)) with large buttons/text for elderly accessibility

## Common Modification Patterns

### Adding a New Command
1. Check command in `/get_response()` with `user_input.startswith("your command")`
2. Parse parameters, validate input
3. Update database if needed (use `conn.commit()`)
4. Set `response` variable to return to user
5. Log to chat_history: `c.execute("INSERT INTO chat_history...", (user_id, timestamp, 'bot', response))`

### Extending Game Features
- Quiz questions array at [run.py](run.py#L48-L57) is hardcoded; extend list to add more questions
- Game state stored in `user_game_states[user_id]` (dict with keys: `current_index`, `score`)
- Answer validation is case-insensitive, partial match (simplifies elderly user input errors)

### Database Schema Changes
- All migrations must update `init_db()` function to create new tables
- No ORM used; raw SQL with parameterized queries (`?` placeholders) to prevent SQL injection
- Each table query should follow pattern: `open conn → execute → commit → close`

## Performance & Constraints

- **Model Memory**: DialoGPT loads into RAM (~2GB); no unloading during runtime
- **Voice Model**: Vosk model (100MB+) bundled in Docker; no cloud dependency means offline-first design
- **Conversation Tokens**: Capped at 1024 tokens to prevent unbounded memory growth; older messages dropped
- **Database**: Single `.db` file with potential write contention; suitable for single-user or low-concurrency
- **Elderly UX**: Voice-first interaction is primary; text is fallback. Large UI elements critical.

## Files to Know
- **[run.py](run.py)** (372 lines): Backend entry point, all routes, model loading, database logic
- **[templates/chat.html](templates/chat.html)** (326 lines): Main UI, JavaScript audio capture, AJAX calls
- **[static/style.css](static/style.css)** (235 lines): Accessibility-focused styling (colors, button sizes, gradients)
- **Dockerfile**: Multi-stage build, Vosk model pre-download in builder stage
- **voice_models/vosk-model-small-en-us-0.15**: Pre-trained offline English speech model

## Session Management
- `session['user_id']` set on successful login/register
- `@login_required` decorator redirects unauthenticated users
- No persistent auth tokens; session revoked on logout or browser close
- Secret key rotated per app restart (not persisted)

## GitHub Copilot Claude Model Support

To enable **Claude 3.5 Sonnet** model in VS Code's GitHub Copilot Chat:

### Step 1: Update Extensions
1. Open VS Code
2. Go to **Extensions** (`Cmd+Shift+X` on macOS)
3. Search for **"GitHub Copilot Chat"** and **"GitHub Copilot"**
4. Click **Update** if available (must be on v1.220+ for Claude support)
5. Reload VS Code (`Cmd+Shift+P` → "Reload Window")

### Step 2: Enable Third-Party Model Providers
1. Visit [github.com/settings/copilot](https://github.com/settings/copilot)
2. Scroll to **"Chat Model Preferences"** section
3. Toggle **"Anthropic Claude"** to **ON** (Enable)
4. If you see **"Google Gemini"**, toggle that too (optional)
5. Click **Save**

### Step 3: Select Claude in VS Code
1. Open Copilot Chat panel in VS Code (`Cmd+Shift+L`)
2. Look for the **model selector** (usually a dropdown arrow at the top of the chat window or bottom-right)
3. Select **"Claude 3.5 Sonnet"** from the dropdown
4. Start chatting!

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Claude option not visible | (1) Restart VS Code; (2) Check that Copilot Chat is v1.220+; (3) Verify GitHub account has been logged in (Cmd+Shift+P → "GitHub: Sign In") |
| "Model not available" error | Check [github.com/settings/copilot](https://github.com/settings/copilot) — Anthropic toggle may have been disabled or your account tier doesn't support it |
| Enterprise/Org restrictions | Your GitHub organization admin may have disabled third-party models. Contact your admin to enable "Anthropic Claude" in org policy |
| Still seeing only GPT-4? | Hard-clear cache: (1) Close VS Code; (2) Delete `~/.vscode/copilot-cache` (if exists); (3) Reopen VS Code |

---

**Last Updated**: March 2026 | **Stack**: FastAPI + SQLite + DialoGPT + Vosk + Bootstrap 5
