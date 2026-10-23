// Thin wrapper around window.TLTSpeech, loaded from /static/speech.js in
// app/layout.tsx — see that file's comment for why this isn't a
// reimplementation.
declare global {
  interface Window {
    TLTSpeech?: {
      speak: (text: string, lang: string, options?: { enabled?: boolean; queue?: boolean }) => void;
    };
  }
}

export function speakText(text: string, lang: string, enabled: boolean, queue = false) {
  window.TLTSpeech?.speak(text, lang, { enabled, queue });
}

/** Sentences of `text` that are finished and not yet spoken (from index `from`),
 * and where to resume. A sentence ends at 。！？ ! ? a newline, or a full stop
 * followed by a space; the unfinished tail waits for more words. Used to start
 * speaking a streamed reply after its first sentence instead of after all of it. */
export function nextSentences(text: string, from: number): { sentences: string[]; next: number } {
  const sentences: string[] = [];
  const end = /[。！？!?\n]+|\.(?=\s)/g;
  end.lastIndex = from;
  let start = from;
  let m: RegExpExecArray | null;
  while ((m = end.exec(text)) !== null) {
    const stop = m.index + m[0].length;
    const piece = text.slice(start, stop).trim();
    if (piece) sentences.push(piece);
    start = stop;
  }
  return { sentences, next: start };
}
