// Thin wrapper around window.TLTSpeech, loaded from /static/speech.js in
// app/layout.tsx — see that file's comment for why this isn't a
// reimplementation.
declare global {
  interface Window {
    TLTSpeech?: {
      speak: (text: string, lang: string, options?: { enabled?: boolean }) => void;
    };
  }
}

export function speakText(text: string, lang: string, enabled: boolean) {
  window.TLTSpeech?.speak(text, lang, { enabled });
}
