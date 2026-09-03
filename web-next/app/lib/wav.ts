// Hand-rolled 16-bit mono WAV encoder, ported near-verbatim from
// static/chat.js's encodeWavFromAudioBuffer — used by the STT fallback
// path (browsers without Web Speech API) to convert a MediaRecorder
// blob into the WAV format /transcribe expects.

export function encodeWavFromAudioBuffer(audioBuffer: AudioBuffer): Blob {
  const channelCount = audioBuffer.numberOfChannels;
  const sampleRate = audioBuffer.sampleRate;
  const length = audioBuffer.length;
  const mixed = new Float32Array(length);

  for (let c = 0; c < channelCount; c++) {
    const channel = audioBuffer.getChannelData(c);
    for (let i = 0; i < length; i++) mixed[i] += channel[i] / channelCount;
  }

  const bytesPerSample = 2;
  const blockAlign = bytesPerSample;
  const byteRate = sampleRate * blockAlign;
  const dataSize = mixed.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  let offset = 0;
  const writeString = (s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset++, s.charCodeAt(i));
  };

  writeString("RIFF");
  view.setUint32(offset, 36 + dataSize, true);
  offset += 4;
  writeString("WAVE");
  writeString("fmt ");
  view.setUint32(offset, 16, true);
  offset += 4;
  view.setUint16(offset, 1, true);
  offset += 2; // PCM
  view.setUint16(offset, 1, true);
  offset += 2; // mono
  view.setUint32(offset, sampleRate, true);
  offset += 4;
  view.setUint32(offset, byteRate, true);
  offset += 4;
  view.setUint16(offset, blockAlign, true);
  offset += 2;
  view.setUint16(offset, 16, true);
  offset += 2;
  writeString("data");
  view.setUint32(offset, dataSize, true);
  offset += 4;

  for (let i = 0; i < mixed.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, mixed[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export async function convertRecordedBlobToWav(blob: Blob): Promise<Blob> {
  const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioCtx) throw new Error("AudioContext not available");
  const ctx = new AudioCtx();
  try {
    const arr = await blob.arrayBuffer();
    const decoded = await ctx.decodeAudioData(arr.slice(0));
    return encodeWavFromAudioBuffer(decoded);
  } finally {
    try {
      await ctx.close();
    } catch {
      // already closed
    }
  }
}
