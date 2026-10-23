"use client";

import Link from "next/link";
import { useSessionLang } from "../lib/useSessionLang";

// Version shown here must match PRIVACY_NOTICE_VERSION in app/core/config.py.
const NOTICE_VERSION = "2026-10";
const CONTACT = process.env.NEXT_PUBLIC_PRIVACY_CONTACT;

const CONTENT = {
  en: {
    title: "Privacy Notice",
    intro: "The Listening Tree is a companion chat app. This page says what we keep, why, for how long, and how you can take it back.",
    sections: [
      ["What we keep", "Your email address, a name if you set one, your password (stored only as a salted hash, never readable), your chat messages and conversation titles, your reminders, your language choice, and a security log of sign-in events (time, approximate network address, browser type)."],
      ["Why", "To run your account and let you continue conversations and reminders; and to detect and stop attacks on accounts. We do not sell your data and do not use it for advertising."],
      ["Who else sees it", "What you type in chat is sent to an AI service (Zhipu AI) to write a reply. Voice you record is sent to a speech-to-text service (Hugging Face, or Google as a fallback) to become text. Sign-in emails go through our email provider. Hosting is on Vercel and Supabase."],
      ["How long", "Old chat messages are removed in stages: older ones are hidden first and erased about 30 days later. Verification codes are erased within a day or two. Security-log entries are erased after 180 days. Your account data stays until you delete your account."],
      ["Your choices", "On your Profile page you can download all your data as a file, and delete your account. Deleting erases your account, chats, reminders and preferences straight away."],
      ["Not for emergencies", "This app is not a medical or crisis service. In an emergency call 999. Samaritans (24 hours, free, private): 2896 0000."],
    ],
    contact: "Questions or requests: ",
    version: "Notice version",
  },
  "zh-HK": {
    title: "私隱聲明",
    intro: "「聆聽樹」係一個陪伴傾偈嘅應用程式。呢頁講明我哋儲存咩資料、點解儲、儲幾耐，同你點樣拎返。",
    sections: [
      ["我哋儲存咩", "你嘅電郵地址、你設定嘅名稱、密碼（只以加鹽雜湊形式儲存，冇人睇得到原文）、對話內容同標題、提醒事項、語言選擇，以及登入安全紀錄（時間、大約網絡位址、瀏覽器類型）。"],
      ["點解要儲", "用嚟營運你嘅帳戶，等你可以延續對話同提醒；亦用嚟偵測同阻止帳戶被攻擊。我哋唔會出售你嘅資料，亦唔會用嚟做廣告。"],
      ["仲有邊個會見到", "你喺對話輸入嘅內容會傳送去人工智能服務（智譜 AI）生成回覆；你錄嘅語音會傳送去語音轉文字服務（Hugging Face，後備為 Google）。登入電郵經我哋嘅電郵供應商寄出。系統託管喺 Vercel 同 Supabase。"],
      ["儲幾耐", "舊對話分階段清走：先隱藏，大約 30 日後徹底刪除。驗證碼一至兩日內刪除。安全紀錄 180 日後刪除。帳戶資料保留至你刪除帳戶為止。"],
      ["你可以點做", "喺「個人檔案」頁可以下載你所有資料，亦可以刪除帳戶。刪除後，帳戶、對話、提醒同偏好設定會即時永久清除。"],
      ["並非緊急服務", "呢個應用程式唔係醫療或危機輔導服務。有緊急情況請打 999。撒瑪利亞防止自殺會（24 小時、免費、保密）：2896 0000。"],
    ],
    contact: "查詢或要求：",
    version: "聲明版本",
  },
} as const;

export default function PrivacyPage() {
  const lang = useSessionLang();
  const c = lang === "zh-HK" ? CONTENT["zh-HK"] : CONTENT.en;
  return (
    <main style={{ maxWidth: 760, margin: "0 auto", padding: "24px 16px", lineHeight: 1.7, fontSize: "1.1rem" }}>
      <h1>{c.title}</h1>
      <p>{c.intro}</p>
      {c.sections.map(([heading, body]) => (
        <section key={heading}>
          <h2>{heading}</h2>
          <p>{body}</p>
        </section>
      ))}
      {CONTACT && (
        <p>
          {c.contact}
          <a href={`mailto:${CONTACT}`}>{CONTACT}</a>
        </p>
      )}
      <p>
        <small>
          {c.version}: {NOTICE_VERSION}
        </small>
      </p>
      <p>
        <Link href="/">←</Link>
      </p>
    </main>
  );
}
