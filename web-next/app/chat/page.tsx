"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "../lib/api";
import { initCapacitorBridge } from "../lib/capacitor";
import {
  createConversation,
  fetchChatHistory,
  fetchConversationMessages,
  fetchConversations,
  sendChatMessage,
  type ChatHistoryItem,
} from "../lib/chat";
import { useTranslations } from "../lib/i18n";
import { speakText } from "../lib/tts";
import { useRequireAuth } from "../lib/useRequireAuth";
import { useTheme } from "../lib/useTheme";
import CalendarCard from "./components/CalendarCard";
import NewsCard from "./components/NewsCard";
import ReminderPanel from "./components/ReminderPanel";
import VoiceRecorder, { type MicState } from "./components/VoiceRecorder";

interface DisplayMessage {
  sender: "user" | "bot";
  text: string;
  time: string;
}

function nowTime(): string {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function toDisplay(history: ChatHistoryItem[]): DisplayMessage[] {
  return history.map((item) => ({
    sender: item.sender,
    text: item.message,
    time: item.timestamp.split(" ")[1]?.slice(0, 5) ?? "",
  }));
}

export default function ChatPage() {
  const { user, checking } = useRequireAuth();
  const lang = user?.lang ?? "en";
  const { t, translations } = useTranslations(lang);

  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [micState, setMicState] = useState<MicState>("idle");
  const [conversationId, setConversationId] = useState<number | null>(null);
  const { theme, toggleTheme } = useTheme();
  const [guideOpen, setGuideOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [offline, setOffline] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const messagesRef = useRef<HTMLDivElement>(null);
  const loadedRef = useRef(false);

  const speak = useCallback(
    (text: string) => {
      speakText(text, lang, ttsEnabled);
    },
    [lang, ttsEnabled]
  );

  // ---- Capacitor native bridge: no-ops in a plain browser ----
  useEffect(() => {
    initCapacitorBridge();
  }, []);

  // ---- history: ?conversation_id= deep link, else most recent, else new ----
  useEffect(() => {
    if (!user || loadedRef.current) return;
    loadedRef.current = true;

    async function load() {
      const requested = new URLSearchParams(window.location.search).get("conversation_id");
      try {
        if (requested) {
          const id = parseInt(requested, 10);
          setConversationId(id);
          setMessages(toDisplay(await fetchConversationMessages(id)));
          return;
        }
        const conversations = await fetchConversations();
        if (conversations.length > 0) {
          const id = conversations[0].id;
          setConversationId(id);
          setMessages(toDisplay(await fetchConversationMessages(id)));
        } else {
          const id = await createConversation();
          setConversationId(id);
          setMessages([]);
        }
      } catch {
        // Fall back to the legacy flat log rather than showing nothing.
        try {
          setMessages(toDisplay(await fetchChatHistory()));
        } catch {
          setMessages([]);
        }
      }
    }
    load();
  }, [user]);

  useEffect(() => {
    const el = messagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // ---- connectivity banner ----
  useEffect(() => {
    function update() {
      setOffline(!navigator.onLine);
    }
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  async function handleSend(e?: React.FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text) return;
    const time = nowTime();
    setMessages((prev) => [...prev, { sender: "user", text, time }]);
    setInput("");
    try {
      const reply = await sendChatMessage(text, conversationId);
      setMessages((prev) => [...prev, { sender: "bot", text: reply, time }]);
      speak(reply);
    } catch {
      setMessages((prev) => [...prev, { sender: "bot", text: t("error_generic", "Something went wrong."), time }]);
    }
  }

  async function handleNewConversation() {
    try {
      const id = await createConversation();
      setConversationId(id);
      setMessages([]);
    } catch {
      // Keep the current conversation open on failure.
    }
  }

  function showToast(message: string) {
    setToast(message);
    setTimeout(() => setToast(null), 3000);
  }

  const placeholder =
    micState === "recording"
      ? t("recording", "Listening... speak now")
      : micState === "processing"
        ? t("processing", "Processing...")
        : t("type_message", "Type your message...");

  if (checking || !user) return null;

  const welcome = t("welcome_chat", "Hello! I am your friendly companion. How are you today? 😊");
  const shown: DisplayMessage[] = messages.length > 0 ? messages : [{ sender: "bot", text: welcome, time: nowTime() }];

  return (
    <div className="page-chat" data-theme={theme}>
      {offline && (
        <div className="alert alert-warning text-center small py-1 mb-0" style={{ zIndex: 9999, position: "sticky", top: 0 }}>
          <i className="fas fa-wifi-slash" /> {t("offline_mode", "Offline - Connection Limited")}
        </div>
      )}

      <div className="main-layout">
        {/* ===== LEFT: Chat Column ===== */}
        <div className="chat-column">
          <div className="chat-card">
            <div className="msg_head">
              <div className="d-flex align-items-center">
                <img src={`${API_BASE}/static/Chatbot.png`} className="user_img" alt="Bot" />
                <div className="user_info ms-3">
                  <span>🌳 {t("app_name", "The Listening Tree")}</span>
                  <p>{t("tagline", "Your friendly companion")}</p>
                </div>
                <div className="ms-auto d-flex gap-2 align-items-center">
                  <button className="btn btn-sm btn-outline-light d-lg-none" type="button" onClick={() => setSidebarOpen((v) => !v)}>
                    <i className="fas fa-columns" />
                  </button>
                  <button id="guideFab" className="btn btn-sm btn-outline-light" type="button" title={t("guide_helper", "Guide Helper")} onClick={() => setGuideOpen((v) => !v)}>
                    <i className="fas fa-question-circle" />
                  </button>
                  <button id="themeToggle" className="btn btn-sm btn-outline-light theme-toggle" type="button" title={t("theme_toggle", "Toggle Theme")} onClick={toggleTheme}>
                    <i className={theme === "dark" ? "fas fa-moon" : "fas fa-sun"} />
                  </button>
                  <a href="/history" className="btn btn-sm btn-outline-light" title={t("conversation_history_title", "Conversation History")}>
                    <i className="fas fa-clock-rotate-left" />
                  </a>
                  <a href="/profile" className="btn btn-sm btn-outline-light" title={t("profile_nav", "My Profile")}>
                    <i className="fas fa-user-circle" />
                  </a>
                  <a href={`${API_BASE}/logout`} className="btn btn-sm btn-danger">
                    {t("logout", "Logout")}
                  </a>
                </div>
              </div>
            </div>

            <div className="chat-nav-bar">
              <a href={`${API_BASE}/set_language/en`} className={`chat-nav-btn${lang === "en" ? " active" : ""}`}>
                EN
              </a>
              <a href={`${API_BASE}/set_language/zh-HK`} className={`chat-nav-btn${lang === "zh-HK" ? " active" : ""}`}>
                繁中
              </a>
              <a href="/accessibility" className="chat-nav-btn nav-icon" title={t("accessibility_mode", "Accessibility Mode")}>
                <i className="fas fa-universal-access" />
              </a>
              <a href="/hk_guide" className="chat-nav-btn" title={t("hk_guide_nav", "HK Guide")}>
                <i className="fas fa-map-marked-alt" /> <span className="d-none d-sm-inline">{t("hk_guide_nav", "HK Guide")}</span>
              </a>
              <button
                type="button"
                className={`chat-nav-btn nav-tts ${ttsEnabled ? "tts-on" : "tts-off"}`}
                title={t("toggle_speech", "Toggle text-to-speech")}
                onClick={() => {
                  setTtsEnabled((prev) => {
                    if (prev) window.speechSynthesis?.cancel();
                    return !prev;
                  });
                }}
              >
                <i className={ttsEnabled ? "fas fa-volume-up" : "fas fa-volume-mute"} />
                <span>{ttsEnabled ? t("voice_on", "🔊 AI Voice: ON") : t("voice_off", "🔇 AI Voice: OFF")}</span>
              </button>
            </div>

            <div className="chat-drop-zone">
              <div className="msg_card_body" ref={messagesRef}>
                {shown.map((m, i) => (
                  <div key={i} className={`d-flex ${m.sender === "bot" ? "justify-content-start" : "justify-content-end"} mb-4 fade-in`}>
                    {m.sender === "bot" && (
                      <div className="img_cont_msg">
                        <img src={`${API_BASE}/static/Chatbot.png`} className="rounded-circle user_img_msg" alt="" />
                      </div>
                    )}
                    <div className={m.sender === "bot" ? "msg_cotainer" : "msg_cotainer_send"}>
                      {m.text}
                      <span className="msg_time">{m.time}</span>
                    </div>
                    {m.sender === "user" && (
                      <div className="img_cont_msg">
                        <img src={`${API_BASE}/static/User.png`} className="rounded-circle user_img_msg" alt="" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="chat-footer">
              <form className="d-flex align-items-center" onSubmit={handleSend}>
                <input
                  type="text"
                  className="type_msg"
                  placeholder={placeholder}
                  autoComplete="off"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    // Explicit rather than relying on the form's implicit
                    // Enter submission, which the mic/discard buttons
                    // sitting inside the same form make easy to break.
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />
                <VoiceRecorder
                  lang={lang}
                  onStateChange={setMicState}
                  onToast={showToast}
                  onTranscript={(text) => setInput(text)}
                />
                <button type="submit" className="send_btn" title={t("send", "Send")}>
                  <i className="fas fa-paper-plane" />
                </button>
              </form>
            </div>
          </div>
        </div>

        {/* ===== RIGHT: Sidebar Column ===== */}
        <div className={`sidebar-column${sidebarOpen ? " show" : ""}`}>
          <div className="sidebar-card conversations-card">
            <div className="sidebar-card-header">
              <i className="fas fa-comment-dots" /> {t("conversations", "Conversations")}
              <button
                onClick={handleNewConversation}
                title={t("new_conversation", "New conversation")}
                style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--primary)", cursor: "pointer", fontSize: "0.85rem" }}
              >
                <i className="fas fa-plus" />
              </button>
            </div>
            <div className="sidebar-card-body" style={{ padding: "10px 12px" }}>
              <a href="/history" className="btn btn-sm btn-outline-secondary w-100">
                <i className="fas fa-clock-rotate-left" /> {t("view_all_conversations", "View all conversations")}
              </a>
            </div>
          </div>

          <CalendarCard lang={lang} title={t("calendar", "Calendar")} onSpeak={speak} />

          <ReminderPanel lang={lang} translations={translations} t={t} />

          <NewsCard t={t} onSpeak={speak} />
        </div>
      </div>

      <div className={`guide-panel${guideOpen ? " show" : ""}`}>
        <div className="guide-panel-header">
          <h3>
            <i className="fas fa-book-open" /> {t("guide_title", "Operation Guide")}
          </h3>
          <button className="guide-panel-close" onClick={() => setGuideOpen(false)}>
            <i className="fas fa-times" />
          </button>
        </div>
        <div className="guide-panel-body">
          <div className="guide-item">
            <h4>
              <i className="fas fa-comments" /> {t("guide_chat_title", "Chat")}
            </h4>
            <p>{t("guide_chat_desc", "Type a message or press the microphone button to talk.")}</p>
          </div>
          <div className="guide-item">
            <h4>
              <i className="fas fa-microphone" /> {t("guide_voice_title", "Voice Input")}
            </h4>
            <p>{t("guide_voice_desc", "Press the mic button, speak clearly.")}</p>
          </div>
          <div className="guide-item">
            <h4>
              <i className="fas fa-bell" /> {t("guide_reminder_title", "Set Reminders")}
            </h4>
            <p>{t("guide_reminder_desc", 'Type "set reminder take medicine 09:00".')}</p>
          </div>
          <div className="guide-item">
            <h4>
              <i className="fas fa-gamepad" /> {t("guide_game_title", "Play Games")}
            </h4>
            <p>{t("guide_game_desc", 'Type "play game" to start a quiz.')}</p>
          </div>
          <div className="guide-item">
            <h4>
              <i className="fas fa-palette" /> {t("guide_theme_title", "Switch Theme")}
            </h4>
            <p>{t("guide_theme_desc", "Click the sun/moon icon.")}</p>
          </div>
          <div className="guide-item">
            <h4>
              <i className="fas fa-globe" /> {t("guide_lang_title", "Change Language")}
            </h4>
            <p>{t("guide_lang_desc", "Click EN or 繁中.")}</p>
          </div>
        </div>
      </div>

      {toast && <div className="voice-toast show">{toast}</div>}
    </div>
  );
}
