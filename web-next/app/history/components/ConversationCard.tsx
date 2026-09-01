"use client";

import { useRef, useState } from "react";
import type { Conversation } from "../../lib/api";
import { renameConversation, setConversationTag, togglePin } from "../../lib/api";
import { CONVERSATION_TAGS, type Translations } from "../../lib/translations";

interface ConversationCardProps {
  conversation: Conversation;
  translations: Translations;
  onUpdate: (updated: Conversation) => void;
  activeFilter: string;
}

export default function ConversationCard({
  conversation,
  translations,
  onUpdate,
  activeFilter,
}: ConversationCardProps) {
  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState(conversation.title);
  // Mirrors the original jQuery version's `$input.off('blur')` guard: Enter
  // and Escape both already decide the outcome (save or cancel), so the
  // blur handler that normally fires right after the input is hidden must
  // not also save — otherwise Escape's cancel gets silently overwritten by
  // a stale blur-save. This ref is the React equivalent of that guard.
  const handledRef = useRef(false);

  async function handlePin() {
    const { pinned } = await togglePin(conversation.id);
    onUpdate({ ...conversation, pinned });
  }

  function startEdit() {
    setDraftTitle(conversation.title);
    handledRef.current = false;
    setEditing(true);
  }

  async function save(title: string) {
    try {
      const { title: saved } = await renameConversation(conversation.id, title);
      onUpdate({ ...conversation, title: saved });
    } finally {
      setEditing(false);
    }
  }

  function cancel() {
    setEditing(false);
  }

  async function handleTagChange(newTag: string) {
    const { tag } = await setConversationTag(conversation.id, newTag);
    onUpdate({ ...conversation, tag });
    // Matches the jQuery version: re-render is only strictly necessary
    // when the active filter is tag-based (changing the tag may remove
    // this card from the current view) — for "all"/"pinned" the parent's
    // state update already covers it.
    void activeFilter;
  }

  return (
    <div className="conv-card">
      <button
        type="button"
        className={`conv-pin-btn${conversation.pinned ? " pinned" : ""}`}
        title={conversation.pinned ? translations.unpin_conversation ?? "Unpin" : translations.pin_conversation ?? "Pin"}
        onClick={handlePin}
      >
        <i className="fas fa-star" />
      </button>

      <div className="conv-main">
        <div className="conv-title-row">
          {editing ? (
            <input
              autoFocus
              type="text"
              className="conv-title-input"
              value={draftTitle}
              onChange={(e) => setDraftTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handledRef.current = true;
                  void save(draftTitle);
                } else if (e.key === "Escape") {
                  handledRef.current = true;
                  cancel();
                }
              }}
              onBlur={() => {
                if (handledRef.current) {
                  handledRef.current = false;
                  return;
                }
                void save(draftTitle);
              }}
            />
          ) : (
            <>
              <a className="conv-title" href={`http://localhost:5000/?conversation_id=${conversation.id}`}>
                {conversation.title}
              </a>
              <button
                type="button"
                className="conv-edit-btn"
                title={translations.rename_conversation ?? "Rename"}
                onClick={startEdit}
              >
                <i className="fas fa-pen" />
              </button>
            </>
          )}
        </div>
        <div className="conv-meta">{conversation.updated_at}</div>
      </div>

      <select
        className="conv-tag-select"
        value={conversation.tag ?? ""}
        onChange={(e) => void handleTagChange(e.target.value)}
      >
        <option value="">{translations.no_tag ?? "No tag"}</option>
        {Object.keys(CONVERSATION_TAGS).map((key) => (
          <option key={key} value={key}>
            {translations[`tag_${key}`] ?? key}
          </option>
        ))}
      </select>
    </div>
  );
}
