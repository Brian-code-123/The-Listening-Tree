"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE, fetchConversations, type Conversation } from "../lib/api";
import { fetchTranslations, type Translations } from "../lib/translations";
import FilterBar from "./components/FilterBar";
import ConversationCard from "./components/ConversationCard";

export default function HistoryPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [translations, setTranslations] = useState<Translations>({});
  const [activeFilter, setActiveFilter] = useState("all");
  // Lazy initializer (not a mount effect) so this doesn't trigger an extra
  // render just to apply the saved theme — reads localStorage safely since
  // this runs both during SSR (window undefined, falls back to "light")
  // and again on the client during hydration.
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof window === "undefined") return "light";
    return localStorage.getItem("theme") === "dark" ? "dark" : "light";
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [convData, tData] = await Promise.all([
          fetchConversations(),
          fetchTranslations("en"),
        ]);
        if (cancelled) return;
        setConversations(convData.conversations);
        setTranslations(tData);
      } catch (e) {
        if (!cancelled) {
          const hint = API_BASE
            ? `is the backend running at ${API_BASE}, and are you logged in there?`
            : "are you logged in?";
          setError(e instanceof Error ? `${e.message} — ${hint}` : "Failed to load.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    if (typeof window !== "undefined") localStorage.setItem("theme", next);
  }

  function updateConversation(updated: Conversation) {
    setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  }

  const filtered = useMemo(() => {
    return conversations.filter((c) => {
      if (activeFilter === "all") return true;
      if (activeFilter === "pinned") return c.pinned;
      return c.tag === activeFilter;
    });
  }, [conversations, activeFilter]);

  return (
    <div className="page-history" data-theme={theme}>
      <button className="theme-toggle" onClick={toggleTheme} title={translations.theme_toggle ?? "Toggle Theme"}>
        <i className={theme === "dark" ? "fas fa-moon" : "fas fa-sun"} />
      </button>

      <nav className="hk-guide-nav">
        <div className="hk-guide-nav-inner">
          <a href={`${API_BASE}/`} className="hk-guide-back-btn" title={translations.conversation_history_back ?? "Back to Chat"}>
            <i className="fas fa-arrow-left" />
            <span>{translations.conversation_history_back ?? "Back to Chat"}</span>
          </a>
          <h1 className="hk-guide-title">
            <i className="fas fa-clock-rotate-left" />
            {translations.conversation_history_title ?? "Conversation History"}
            <span style={{ fontSize: "0.6em", fontWeight: 400, color: "var(--text-muted)", marginLeft: 8 }}>
              (Next.js POC)
            </span>
          </h1>
          <div className="hk-guide-lang">
            <span className="chat-nav-btn active">EN</span>
          </div>
        </div>
      </nav>

      <main>
        <FilterBar active={activeFilter} onChange={setActiveFilter} translations={translations} />

        {loading && <div className="empty-state">Loading…</div>}
        {error && (
          <div className="empty-state" style={{ color: "var(--accent)" }}>
            {error}
          </div>
        )}

        {!loading && !error && (
          <>
            <div>
              {filtered.map((conv) => (
                <ConversationCard
                  key={conv.id}
                  conversation={conv}
                  translations={translations}
                  onUpdate={updateConversation}
                  activeFilter={activeFilter}
                />
              ))}
            </div>
            {filtered.length === 0 && (
              <div className="empty-state">{translations.no_conversations ?? "No conversations yet."}</div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
