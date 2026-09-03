import { API_BASE } from "./api";

/** POST /transcribe — the STT-fallback engine's server round trip, used
 * when the browser has no Web Speech API. */
export async function transcribeAudio(wavBlob: Blob, lang: string): Promise<string> {
  const form = new FormData();
  form.append("audio", wavBlob, "speech.wav");
  form.append("lang", lang);
  const res = await fetch(`${API_BASE}/transcribe`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || "STT request failed");
  }
  return (data.text || "").trim();
}
