"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "../lib/api";
import { CATEGORY_COLOR, CATEGORY_ICON, fetchHkGuide, type HkGuideItem } from "../lib/hkGuide";
import { useTranslations } from "../lib/i18n";
import { speakText } from "../lib/tts";
import { useRequireAuth } from "../lib/useRequireAuth";

const CATEGORIES = ["all", "food", "shopping", "fun", "events"] as const;
type Category = (typeof CATEGORIES)[number];

export default function HkGuidePage() {
  const { t } = useTranslations();
  const { user, checking } = useRequireAuth();

  const [items, setItems] = useState<HkGuideItem[]>([]);
  const [lastUpdated, setLastUpdated] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [category, setCategory] = useState<Category>("all");
  const [detailItem, setDetailItem] = useState<HkGuideItem | null>(null);
  const loadedRef = useRef(false);

  async function load(refresh = false) {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    try {
      const data = await fetchHkGuide(refresh);
      setItems(data.items || []);
      setLastUpdated(data.last_updated || "");
    } catch {
      // Leave whatever's already loaded; the empty/loading state below
      // covers the first-load failure case.
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    if (!user || loadedRef.current) return;
    loadedRef.current = true;
    load();
    const interval = setInterval(() => load(), 15 * 60 * 1000);
    return () => clearInterval(interval);
  }, [user]);

  useEffect(() => {
    if (!detailItem) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setDetailItem(null);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [detailItem]);

  if (checking || !user) {
    return null;
  }

  const filtered = category === "all" ? items : items.filter((i) => i.category === category);

  function categoryLabel(cat: string): string {
    return t(`hk_guide_${cat}`, cat);
  }

  return (
    <div className="page-hk-guide" data-theme="light">
      <nav className="hk-guide-nav">
        <div className="hk-guide-nav-inner">
          <a href={`${API_BASE}/`} className="hk-guide-back-btn" title={t("hk_guide_back", "Back to Chat")}>
            <i className="fas fa-arrow-left" /> <span>{t("hk_guide_back", "Back to Chat")}</span>
          </a>
          <h1 className="hk-guide-title">
            <i className="fas fa-map-marked-alt" /> <span>{t("hk_guide_title", "Hong Kong Local Guide")}</span>
          </h1>
          <div className="hk-guide-lang">
            <a href="/set_language/en" className="chat-nav-btn active">
              EN
            </a>
            <a href="/set_language/zh-HK" className="chat-nav-btn">
              繁中
            </a>
          </div>
        </div>
      </nav>

      <div className="hk-guide-tabs">
        {CATEGORIES.map((cat) => (
          <button key={cat} className={`hk-tab${category === cat ? " active" : ""}`} onClick={() => setCategory(cat)}>
            <i className={`fas ${cat === "all" ? "fa-globe-asia" : CATEGORY_ICON[cat]}`} /> {categoryLabel(cat === "all" ? "all" : cat)}
          </button>
        ))}
      </div>

      <div className="hk-guide-update-bar">
        <span>
          <i className="fas fa-clock" />{" "}
          {loading ? t("hk_guide_loading", "Loading latest info...") : `${t("hk_guide_last_updated", "Last updated:")} ${lastUpdated}`}
        </span>
        <button className="hk-refresh-btn" onClick={() => load(true)} title={t("refresh_news", "Refresh")}>
          <i className={`fas fa-sync-alt${refreshing ? " fa-spin" : ""}`} /> {t("refresh_news", "Refresh")}
        </button>
      </div>

      <div className="hk-guide-container">
        {loading ? (
          <div className="hk-guide-loading">
            <i className="fas fa-spinner fa-spin fa-2x" />
            <p>{t("hk_guide_loading", "Loading latest info...")}</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="hk-guide-empty">
            <i className="fas fa-search fa-2x" />
            <p>{t("hk_guide_empty", "No items found for this category.")}</p>
          </div>
        ) : (
          <div className="hk-guide-grid">
            {filtered.map((item, idx) => (
              <div
                key={idx}
                className="hk-guide-card"
                role="button"
                tabIndex={0}
                onClick={() => setDetailItem(item)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setDetailItem(item);
                  }
                }}
              >
                <div className="hk-card-badge" style={{ background: CATEGORY_COLOR[item.category] }}>
                  <i className={`fas ${CATEGORY_ICON[item.category]}`} /> {categoryLabel(item.category)}
                </div>
                <div className="hk-card-body">
                  <h3 className="hk-card-title">{item.name}</h3>
                  <p className="hk-card-desc">{item.short_desc}</p>
                  {item.location && (
                    <div className="hk-card-location">
                      <i className="fas fa-map-marker-alt" /> {item.location}
                    </div>
                  )}
                  {item.price_range && (
                    <div className="hk-card-price">
                      <i className="fas fa-dollar-sign" /> {item.price_range}
                    </div>
                  )}
                  {item.hours && (
                    <div className="hk-card-hours">
                      <i className="fas fa-clock" /> {item.hours}
                    </div>
                  )}
                </div>
                <div className="hk-card-footer">
                  <button
                    className="hk-card-speak"
                    onClick={(e) => {
                      e.stopPropagation();
                      speakText(`${item.name}. ${item.short_desc}`, "en", true);
                    }}
                    title={t("voice_read", "Read aloud")}
                  >
                    <i className="fas fa-volume-up" />
                  </button>
                  <button
                    className="hk-card-detail"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDetailItem(item);
                    }}
                  >
                    {t("read_more", "Read more")} <i className="fas fa-arrow-right" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className={`hk-guide-modal${detailItem ? " show" : ""}`}>
        <div
          className="hk-guide-modal-overlay"
          role="presentation"
          aria-hidden="true"
          onClick={() => setDetailItem(null)}
        />
        <div className="hk-guide-modal-content">
          <button className="hk-guide-modal-close" onClick={() => setDetailItem(null)}>
            <i className="fas fa-times" />
          </button>
          {detailItem && (
            <div>
              <div className="modal-header-bar" style={{ background: CATEGORY_COLOR[detailItem.category] }}>
                <i className={`fas ${CATEGORY_ICON[detailItem.category]}`} /> {categoryLabel(detailItem.category)}
              </div>
              <div className="modal-detail-body">
                <h2>{detailItem.name}</h2>
                <p className="modal-full-desc">{detailItem.full_desc || detailItem.short_desc}</p>
                {detailItem.location && (
                  <div className="modal-info-row">
                    <i className="fas fa-map-marker-alt" /> <strong>{t("hk_guide_location", "Location:")}</strong> {detailItem.location}
                  </div>
                )}
                {detailItem.price_range && (
                  <div className="modal-info-row">
                    <i className="fas fa-dollar-sign" /> <strong>{t("hk_guide_price", "Price:")}</strong> {detailItem.price_range}
                  </div>
                )}
                {detailItem.hours && (
                  <div className="modal-info-row">
                    <i className="fas fa-clock" /> <strong>{t("hk_guide_hours", "Hours:")}</strong> {detailItem.hours}
                  </div>
                )}
                {detailItem.transport && (
                  <div className="modal-info-row">
                    <i className="fas fa-subway" /> <strong>{t("hk_guide_transport", "Transport:")}</strong> {detailItem.transport}
                  </div>
                )}
                {detailItem.elderly_friendly && (
                  <div className="modal-elderly-badge">
                    <i className="fas fa-wheelchair" /> {t("hk_guide_elderly_friendly", "Elderly Friendly")}
                  </div>
                )}
                {detailItem.tips && detailItem.tips.length > 0 && (
                  <div className="modal-tips">
                    <h4>
                      <i className="fas fa-lightbulb" /> {t("hk_guide_tips", "Tips")}
                    </h4>
                    <ul>
                      {detailItem.tips.map((tip, i) => (
                        <li key={i}>{tip}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {detailItem.url && detailItem.url !== "#" && (
                  <a href={detailItem.url} target="_blank" rel="noopener" className="modal-link-btn">
                    <i className="fas fa-external-link-alt" /> {t("hk_guide_learn_more", "Learn More")}
                  </a>
                )}
                <button
                  className="modal-speak-btn"
                  onClick={() => {
                    let text = `${detailItem.name}. ${detailItem.full_desc || detailItem.short_desc}`;
                    if (detailItem.location) text += `. ${t("hk_guide_location", "Location:")} ${detailItem.location}`;
                    speakText(text, "en", true);
                  }}
                >
                  <i className="fas fa-volume-up" /> {t("hk_guide_read_aloud", "Read Aloud")}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
