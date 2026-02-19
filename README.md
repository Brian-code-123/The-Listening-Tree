# The Listening Tree 🌳

> **Compassionate AI Companion for Elderly Wellness**  
> Bilingual chatbot with glassmorphism UI, voice interaction, and intelligent reminders

[![License](https://img.shields.io/badge/license-Academic-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-green)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/fastapi-0.100%2B-blue)](https://fastapi.tiangolo.com)
[![Status](https://img.shields.io/badge/status-production-brightgreen)](#deployment)

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **🤖 AI-Powered Chat** | Kimi/Moonshot AI API with 8K context window for contextual conversations |
| **🎙️ Voice I/O** | Web Speech API (EN/繁中) + Vosk offline STT; TTS with emotion-aware pacing |
| **📅 Smart Calendar** | FullCalendar.js integration with HK public holidays (2025-2027); voice-readable |
| **⏰ Intelligent Reminders** | Persistent SQLite-backed reminders with system notifications & alarm sound |
| **📰 Local News Feed** | NewsAPI.org integration + hardcoded HK news fallback; 30-min cache |
| **🎮 Memory Games** | Interactive quizzes & trivia for cognitive engagement (expandable) |
| **🎨 Glassmorphism UI** | Apple Liquid Glass design with `backdrop-filter: blur(16px)`; dark/light modes |
| **♿ Accessibility** | WCAG AA contrast (>4.5:1), large touch targets (48px), keyboard navigation |
| **🌍 Bilingual** | Full EN + 繁體中文 (Hong Kong) with live language switching |
| **📱 Responsive** | Mobile-first 3-column layout: chat (left) + sidebar (calendar/reminders/news, right)

---

## 🚀 Quick Start

### Local Development
```bash
# Clone repository
git clone https://github.com/yourusername/The-Listening-Tree.git
cd The-Listening-Tree

# Install dependencies
pip install -r requirements.txt

# Run development server
python run.py
```

Access at: **http://localhost:5000**

### Docker Deployment
```bash
# Build image
docker build -t the-listening-tree .

# Run container
docker run -p 5000:5000 -e ZHIPUAI_API_KEY=your_api_key the-listening-tree
```

### Deploy to Render (Free Tier)
1. Push code to GitHub
2. Connect repository to [Render](https://render.com)
3. Set environment variable: `ZHIPUAI_API_KEY`
4. Render auto-detects `render.yaml` and deploys

---

## 🧬 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|----------|
| **Backend** | Flask 3.0 | Web framework |
| **AI Model** | GLM-4.7-Flash | Conversational AI (30B SOTA, 200K context) |
| **Speech Recognition** | Web Speech API | Browser-side voice input (offline-capable) |
| **Database** | SQLite | User data, reminders, chat history |
| **Frontend** | Bootstrap 5 + Font Awesome | Responsive UI components |
| **Translations** | Python i18n | English & Traditional Chinese (Hong Kong) |
| **Deployment** | Gunicorn + Render | Production WSGI server |

**Project Size**: **4.77 MB** (deployable, excluding dependencies)

---

## 📋 Requirements

- **Python 3.12+**
- **Free ZhipuAI API key** ([Get yours](https://open.bigmodel.cn))
- Modern browser with Web Speech API support (Chrome/Edge recommended)

### Dependencies (requirements.txt)
```txt
flask==3.0.0
flask-wtf==1.2.1
wtforms==3.1.1
email_validator==2.1.0
gunicorn==22.0.0
```

**No heavy ML dependencies!** (PyTorch, Transformers, Vosk removed for lightweight deployment)

---

## 🔑 Configuration

Create `.env` file (copy from `.env.example`):
```bash
ZHIPUAI_API_KEY=your_api_key_here  # Get free key at https://open.bigmodel.cn
FLASK_SECRET_KEY=your_secret_key   # Optional
FLASK_DEBUG=0                      # Set to 1 for development
```

---

## 📁 Project Structure

```
The-Listening-Tree/
├── run.py                 # Main Flask application (755 lines)
├── translations.py        # Bilingual translation strings
├── requirements.txt       # Python dependencies (5 packages)
├── Dockerfile            # Production container config
├── render.yaml           # Render deployment config
├── static/
│   └── style.css         # Consolidated CSS (661 lines, 16KB)
├── templates/
│   ├── chat.html         # Main chat interface
│   ├── accessibility.html # WCAG AAA accessible mode
│   ├── login.html        # Authentication
│   ├── register.html     # User registration
│   └── guidance.html     # User guide & help
└── reminders.db          # SQLite database (auto-created)
```

---

## 🎨 Key Design Principles

1. **Elderly-First UX**: Large buttons (min 44x44px), high contrast, clear typography
2. **Voice-First Interaction**: Microphone as primary input, text as fallback
3. **Zero Cloud Latency**: Web Speech API runs in browser, no server round-trip
4. **Lightweight Architecture**: 4.77 MB deployable size, free hosting compatible
5. **Bilingual from Ground Up**: All UI strings externalized, easy to add languages
6. **WCAG AAA Compliance**: Accessibility mode with skip links, ARIA labels, keyboard navigation

---

## 🌐 Deployment History

- **Current**: Lightweight cloud edition using GLM-4.7-Flash API
- **Previous**: DialoGPT + Vosk (~1GB, deployment-unfriendly)
- **Optimization**: Removed 68MB voice models, 397MB PyTorch, 94MB Transformers
- **Result**: **~95% size reduction** (1GB → 4.77MB)

**Render Deployment**: Auto-deploys from `main` branch via `render.yaml`

---

## 🛠️ Development Commands

```bash
# Install dependencies in virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run development server
python run.py

# Test imports
python -c "import run; print('✓ Import successful')"

# Check project size (excluding .venv)
du -sh --exclude='.venv' --exclude='.git' .
```

---

## 🤝 Contributing

This is a Final Year Project (FYP) for elderly wellness technology research. Contributions welcome via pull requests.

**Key Contribution Areas**:
- Additional language support (e.g., Mandarin, Spanish, Japanese)
- More memory game types (puzzles, music recall, photo matching)
- Integration with health monitoring APIs (Apple Health, Google Fit)
- Advanced reminder scheduling (recurring, snooze, priority levels)

---

## 📜 License

This project is academic software intended for educational and research purposes.

---

## 🙏 Acknowledgments

- **ZhipuAI** for providing free GLM-4.7-Flash API access
- **Web Speech API** (Chrome/Edge) for offline-capable voice recognition
- **Bootstrap Team** for responsive UI framework
- **Flask Community** for excellent web development tools

---

## 📧 Contact

For questions or feature requests, please open an issue on GitHub.

---

**Built with ❤️ for elderly wellness • FYP 2026**
