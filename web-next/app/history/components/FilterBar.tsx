"use client";

import { CONVERSATION_TAGS, type Translations } from "../../lib/translations";

interface FilterBarProps {
  active: string;
  onChange: (filter: string) => void;
  translations: Translations;
}

export default function FilterBar({ active, onChange, translations }: FilterBarProps) {
  return (
    <div className="filter-row">
      <button
        type="button"
        className={`filter-chip${active === "all" ? " active" : ""}`}
        onClick={() => onChange("all")}
      >
        {translations.filter_all ?? "All"}
      </button>
      <button
        type="button"
        className={`filter-chip${active === "pinned" ? " active" : ""}`}
        onClick={() => onChange("pinned")}
      >
        <i className="fas fa-star" /> {translations.filter_pinned ?? "Pinned"}
      </button>
      {Object.entries(CONVERSATION_TAGS).map(([key, meta]) => (
        <button
          type="button"
          key={key}
          className={`filter-chip${active === key ? " active" : ""}`}
          onClick={() => onChange(key)}
        >
          <span className="dot" style={{ background: meta.color }} />
          {translations[`tag_${key}`] ?? key}
        </button>
      ))}
    </div>
  );
}
