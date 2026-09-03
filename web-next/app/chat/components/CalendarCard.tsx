"use client";

import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
// dateClick comes from the interaction plugin. The Jinja page got it for
// free from FullCalendar's all-in-one CDN bundle; the modular build needs
// it listed explicitly or the click-to-speak-a-date handler never fires.
import interactionPlugin from "@fullcalendar/interaction";
import type { EventInput } from "@fullcalendar/core";
import { fetchHkHolidays } from "../../lib/chat";

interface CalendarCardProps {
  lang: string;
  title: string;
  onSpeak: (text: string) => void;
}

// Uses @fullcalendar/react rather than the CDN global the Jinja page
// loads — same plugin, official React wrapper, so the custom
// dayCellContent/dayCellClassNames/eventClick/dateClick behaviour ports
// across unchanged.
export default function CalendarCard({ lang, title, onSpeak }: CalendarCardProps) {
  return (
    <div className="sidebar-card calendar-card">
      <div className="sidebar-card-header">
        <i className="fas fa-calendar-alt" /> {title}
      </div>
      <div className="sidebar-card-body" style={{ padding: "8px 12px" }}>
        <div id="miniCalendar">
          <FullCalendar
            plugins={[dayGridPlugin, interactionPlugin]}
            initialView="dayGridMonth"
            locale={lang === "zh-HK" ? "zh-hk" : "en"}
            headerToolbar={{ left: "prev", center: "title", right: "next" }}
            height="auto"
            fixedWeekCount={false}
            dayMaxEvents={1}
            // Unified date display — the plain day number, without the
            // "日" suffix the zh-hk locale would otherwise add.
            dayCellContent={(arg) => ({ html: String(arg.date.getDate()) })}
            dayCellClassNames={(arg) => (arg.isToday ? ["fc-daygrid-day-today"] : [])}
            events={(_info, success) => {
              fetchHkHolidays()
                .then((holidays) => success(holidays as EventInput[]))
                .catch(() => success([]));
            }}
            eventClick={(info) => onSpeak(info.event.title)}
            dateClick={(info) => {
              const d = new Date(info.dateStr);
              const dateText =
                lang === "zh-HK"
                  ? `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
                  : d.toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
              onSpeak(dateText);
            }}
          />
        </div>
      </div>
    </div>
  );
}
