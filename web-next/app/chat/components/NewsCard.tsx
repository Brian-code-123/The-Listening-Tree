"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchNews, type NewsArticle } from "../../lib/chat";

interface NewsCardProps {
  t: (key: string, fallback: string) => string;
  onSpeak: (text: string) => void;
}

// Built directly against fetch_hk_news's real response shape
// ({articles: [{title, description, source, url}]}). Deliberately NOT a
// port of UI.NewsItem in static/components.js — that helper doesn't match
// what the chat page actually renders and is effectively dead code.
export default function NewsCard({ t, onSpeak }: NewsCardProps) {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  // setState only ever runs inside a promise callback here, never
  // synchronously in the effect body — same shape the other ported pages
  // use for their load-on-mount fetches.
  const load = useCallback(
    () =>
      fetchNews()
        .then((list) => {
          setArticles(list);
          setFailed(false);
        })
        .catch(() => setFailed(true))
        .finally(() => setLoading(false)),
    []
  );

  useEffect(() => {
    load();
  }, [load]);

  function handleRefresh() {
    setLoading(true);
    load();
  }

  return (
    <div className="sidebar-card news-card">
      <div className="sidebar-card-header">
        <i className="fas fa-newspaper" /> {t("hk_news", "Hong Kong News")}
        <button
          onClick={handleRefresh}
          title={t("refresh_news", "Refresh")}
          style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--primary)", cursor: "pointer", fontSize: "0.85rem" }}
        >
          <i className="fas fa-sync-alt" />
        </button>
      </div>
      <div className="sidebar-card-body" id="newsContainer">
        {loading ? (
          <div className="news-loading">
            <i className="fas fa-spinner" /> {t("loading_news", "Loading news...")}
          </div>
        ) : failed || articles.length === 0 ? (
          <p style={{ textAlign: "center", color: "var(--text-muted)", padding: 20, fontSize: "0.9rem" }}>{t("no_news", "No news available.")}</p>
        ) : (
          articles.map((article, i) => (
            <div key={i} className="news-item fade-in" onClick={() => window.open(article.url, "_blank")}>
              <div className="news-title">{article.title}</div>
              <div className="news-desc">{article.description || ""}</div>
              <div className="news-meta">
                <span className="news-source">{article.source}</span>
                <button
                  className="news-voice-btn"
                  title={t("voice_read", "Read aloud")}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSpeak(`${article.title}. ${article.description || ""}`);
                  }}
                >
                  <i className="fas fa-volume-up" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
