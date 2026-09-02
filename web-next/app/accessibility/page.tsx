"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "../lib/api";
import { fetchChatHistory, sendChatMessage, type ChatHistoryItem } from "../lib/chat";
import { useTranslations } from "../lib/i18n";
import { speakText } from "../lib/tts";
import { useRequireAuth } from "../lib/useRequireAuth";

interface DisplayMessage {
  sender: "user" | "bot";
  text: string;
  time: string;
}

function nowTime(): string {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function AccessibilityPage() {
  const { t } = useTranslations();
  const { user, checking } = useRequireAuth();

  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [ttsEnabled, setTtsEnabled] = useState(false);
  const [status, setStatus] = useState<{ message: string; type: "" | "success" | "error" } | null>(null);
  const [recording, setRecording] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const messagesAreaRef = useRef<HTMLDivElement>(null);
  const loadedRef = useRef(false);

  useEffect(() => {
    if (!user || loadedRef.current) return;
    loadedRef.current = true;
    fetchChatHistory()
      .then((history: ChatHistoryItem[]) => {
        setMessages(
          history.map((item) => ({
            sender: item.sender,
            text: item.message,
            time: item.timestamp.split(" ")[1]?.slice(0, 5) ?? "",
          }))
        );
        showStatus(t("page_loaded", "Page loaded. Ready to chat."), "success");
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  useEffect(() => {
    const el = messagesAreaRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  function showStatus(message: string, type: "" | "success" | "error") {
    setStatus({ message, type });
    if (type === "success" || type === "error") {
      setTimeout(() => setStatus(null), 3000);
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text) return;
    const time = nowTime();
    setMessages((prev) => [...prev, { sender: "user", text, time }]);
    setInput("");
    showStatus(t("processing", "Processing..."), "");
    try {
      const reply = await sendChatMessage(text);
      setMessages((prev) => [...prev, { sender: "bot", text: reply, time: nowTime() }]);
      setStatus(null);
      if (ttsEnabled) speakText(reply, "en", true);
    } catch {
      showStatus(t("error_generic", "Something went wrong. Please try again."), "error");
    }
  }

  function clearChat() {
    setMessages([]);
    showStatus(t("chat_cleared", "Chat cleared"), "success");
  }

  function startRecording() {
    const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      showStatus(t("speech_not_supported", "Your browser does not support speech recognition. Please use Chrome or Edge."), "error");
      return;
    }
    const recognition = new SpeechRecognitionCtor();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;

    setRecording(true);
    showStatus(t("recording", "Recording..."), "");

    recognition.addEventListener("result", (event: SpeechRecognitionEvent) => {
      const text = event.results[0][0].transcript;
      if (text) setInput(text);
    });
    recognition.addEventListener("end", () => {
      setRecording(false);
      recognitionRef.current = null;
      setStatus(null);
    });
    recognition.addEventListener("error", (event: SpeechRecognitionErrorEvent) => {
      showStatus(`${t("speech_error", "Speech recognition error:")} ${event.error}`, "error");
    });

    recognition.start();
    recognitionRef.current = recognition;
  }

  function stopRecording() {
    recognitionRef.current?.stop();
  }

  function toggleTts() {
    setTtsEnabled((prev) => {
      const next = !prev;
      showStatus(next ? t("tts_on", "Text-to-speech enabled") : t("tts_off", "Text-to-speech disabled"), next ? "success" : "");
      return next;
    });
  }

  if (checking || !user) {
    return null;
  }

  return (
    <div className="page-accessibility" data-theme="light">
      <a href="#main-content" className="skip-link">
        {t("skip_to_content", "Skip to main content")}
      </a>

      <div className="container-fluid">
        <div className="accessibility-banner" role="banner">
          <div className="accessibility-banner-icon" aria-hidden="true">
            <i className="fas fa-universal-access" />
          </div>
          <h1>{t("accessibility_title", "Enhanced Accessibility Mode")}</h1>
          <p>{t("accessibility_desc", "Optimized for elderly users with visual impairment - Large text, high contrast, voice support")}</p>
        </div>

        <nav className="nav-bar" role="navigation" aria-label={t("main_navigation", "Main navigation")}>
          <h1 className="nav-title">{t("app_name", "The Listening Tree")}</h1>
          <div className="lang-switch" role="group" aria-label={t("language_selector", "Language selector")}>
            <a href="/set_language/en" className="lang-btn active" aria-label="English">
              EN
            </a>
            <a href="/set_language/zh-HK" className="lang-btn" aria-label="繁體中文">
              繁中
            </a>
          </div>
          <div className="nav-buttons" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <a href={`${API_BASE}/`} className="btn-accessible btn-secondary-accessible" aria-label={t("normal_mode", "Switch to normal mode")}>
              <i className="fas fa-desktop" aria-hidden="true" /> <span>{t("normal_mode", "Normal Mode")}</span>
            </a>
            <a href={`${API_BASE}/logout`} className="btn-accessible btn-danger-accessible" aria-label={t("logout", "Logout from application")}>
              <i className="fas fa-sign-out-alt" aria-hidden="true" /> <span>{t("logout", "Logout")}</span>
            </a>
          </div>
        </nav>

        <main id="main-content" className="chat-container" role="main">
          <div className="chat-header">
            <h2>
              <i className="fas fa-comments" aria-hidden="true" /> {t("conversation", "Conversation")}
            </h2>
            <button className="btn-accessible btn-primary-accessible" onClick={clearChat} aria-label={t("clear_chat", "Clear all messages")}>
              <i className="fas fa-eraser" aria-hidden="true" /> <span>{t("clear", "Clear")}</span>
            </button>
          </div>

          <div className="messages-area" ref={messagesAreaRef} role="log" aria-live="polite" aria-label={t("chat_messages", "Chat messages")}>
            {messages.length === 0 ? (
              <div className="message message-bot">
                <div className="message-label">{t("assistant", "Assistant")}</div>
                <div>{t("welcome_message", "Hello! How can I help you today? You can type your message or use voice input.")}</div>
                <div className="message-time">{t("just_now", "Just now")}</div>
              </div>
            ) : (
              messages.map((m, i) => (
                <div key={i} className={`message message-${m.sender}`}>
                  <div className="message-label">{m.sender === "user" ? t("you", "You") : t("assistant", "Assistant")}</div>
                  <div>{m.text}</div>
                  <div className="message-time">{m.time}</div>
                </div>
              ))
            )}
          </div>

          <div className="input-section">
            <div className="input-wrapper">
              <label htmlFor="messageInput" className="visually-hidden">
                {t("type_message", "Type your message")}
              </label>
              <input
                type="text"
                id="messageInput"
                className="input-field"
                placeholder={t("type_here", "Type your message here...")}
                aria-label={t("message_input", "Message input field")}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSend();
                }}
              />
              <button className="btn-accessible btn-primary-accessible" onClick={handleSend} aria-label={t("send_message", "Send message")}>
                <i className="fas fa-paper-plane" aria-hidden="true" /> <span>{t("send", "Send")}</span>
              </button>
            </div>

            <div className="voice-controls">
              <button
                className={`voice-btn voice-btn-record${recording ? " recording" : ""}`}
                onClick={startRecording}
                disabled={recording}
                aria-label={t("start_recording", "Start voice recording")}
              >
                <i className="fas fa-microphone" aria-hidden="true" /> <span>{t("record", "Record")}</span>
              </button>
              <button
                className="voice-btn voice-btn-stop"
                onClick={stopRecording}
                disabled={!recording}
                aria-label={t("stop_recording", "Stop voice recording")}
              >
                <i className="fas fa-stop-circle" aria-hidden="true" /> <span>{t("stop", "Stop")}</span>
              </button>
              <button
                className="btn-accessible btn-success-accessible"
                onClick={toggleTts}
                aria-label={t("toggle_speech", "Toggle text-to-speech")}
                aria-pressed={ttsEnabled}
              >
                <i className="fas fa-volume-up" aria-hidden="true" /> <span>{t("speak", "Speak")}</span>
              </button>
            </div>

            {status && (
              <div className={`status-message${status.type ? ` status-${status.type}` : ""}`} role="status" aria-live="polite">
                <span className="status-icon">
                  <i className="fas fa-info-circle" />
                </span>
                <span>{status.message}</span>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
