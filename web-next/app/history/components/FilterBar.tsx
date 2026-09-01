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
      <div
        className={`filter-chip${active === "all" ? " active" : ""}`}
        onClick={() => onChange("all")}
      >
        {translations.filter_all ?? "All"}
      </div>
      <div
        className={`filter-chip${active === "pinned" ? " active" : ""}`}
        onClick={() => onChange("pinned")}
      >
        <i className="fas fa-star" /> {translations.filter_pinned ?? "Pinned"}
      </div>
      {Object.entries(CONVERSATION_TAGS).map(([key, meta]) => (
        <div
          key={key}
          className={`filter-chip${active === key ? " active" : ""}`}
          onClick={() => onChange(key)}
        >
          <span className="dot" style={{ background: meta.color }} />
          {translations[`tag_${key}`] ?? key}
        </div>
      ))}
    </div>
  );
}
