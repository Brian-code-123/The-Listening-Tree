"use client";

import { useEffect, useRef, useState } from "react";
import { transcribeAudio } from "../../lib/transcribe";
import { convertRecordedBlobToWav } from "../../lib/wav";

export type MicState = "idle" | "recording" | "processing";

interface VoiceRecorderProps {
  lang: string;
  onTranscript: (text: string) => void;
  onStateChange: (state: MicState) => void;
  onToast: (message: string) => void;
}

// Ported near-verbatim from static/chat.js's voice-recording section —
// same two engines (Web Speech API primary, getUserMedia+MediaRecorder+
// /transcribe fallback), same waveform visualization, same discard
// semantics. Kept as one imperative controller (refs, not state, for the
// mutable recording session) rather than force-fitting into React state,
// matching the plan's recommendation to model this explicitly rather
// than risk stale-closure bugs from a naive useState translation.
export default function VoiceRecorder({ lang, onTranscript, onStateChange, onToast }: VoiceRecorderProps) {
  const [micState, setMicState] = useState<MicState>("idle");
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const recordingModeRef = useRef<"webspeech" | "fallback" | null>(null);
  const discardRef = useRef(false);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const mimeTypeRef = useRef("");

  const waveformRef = useRef<{
    synthetic?: boolean;
    audioCtx?: AudioContext;
    analyser?: AnalyserNode;
    dataArray?: Uint8Array<ArrayBuffer>;
    history: number[];
    maxBars: number;
    rafId: number | null;
    lastSampleTime: number;
    startTime?: number;
    stream?: MediaStream;
    ownsStream?: boolean;
  } | null>(null);

  const BAR_PITCH_PX = 4;
  const SAMPLE_INTERVAL_MS = 70;

  function setState(s: MicState) {
    setMicState(s);
    onStateChange(s);
  }

  function drawWaveform(ts?: number) {
    const s = waveformRef.current;
    if (!s) return;
    const prefersReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const interval = prefersReducedMotion ? SAMPLE_INTERVAL_MS * 4 : SAMPLE_INTERVAL_MS;

    if (!ts || ts - s.lastSampleTime >= interval) {
      s.lastSampleTime = ts || 0;
      let amp: number;
      if (s.synthetic) {
        const t = (performance.now() - (s.startTime ?? 0)) / 1000;
        amp = 0.35 + 0.25 * Math.abs(Math.sin(t * 2.2)) + Math.random() * 0.1;
      } else if (s.analyser && s.dataArray) {
        s.analyser.getByteTimeDomainData(s.dataArray);
        let sumSquares = 0;
        for (let i = 0; i < s.dataArray.length; i++) {
          const v = (s.dataArray[i] - 128) / 128;
          sumSquares += v * v;
        }
        const rms = Math.sqrt(sumSquares / s.dataArray.length);
        amp = Math.min(1, rms * 4);
      } else {
        amp = 0;
      }
      s.history.push(amp);
      if (s.history.length > s.maxBars) s.history.shift();
    }

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);

    const minBarHeight = 3;
    ctx.fillStyle = "#5B9A7D";
    const startX = width - s.history.length * BAR_PITCH_PX;
    for (let i = 0; i < s.history.length; i++) {
      const amp = s.history[i];
      const barHeight = Math.max(minBarHeight, amp * height * 0.9);
      const x = startX + i * BAR_PITCH_PX;
      const y = (height - barHeight) / 2;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x, y, BAR_PITCH_PX - 1.5, barHeight, 2);
      else ctx.rect(x, y, BAR_PITCH_PX - 1.5, barHeight);
      ctx.fill();
    }
    s.rafId = requestAnimationFrame(drawWaveform);
  }

  function initWaveformAnalyser(stream: MediaStream, ownsStream: boolean) {
    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;
      const audioCtx = new AudioCtx();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      const canvas = canvasRef.current;
      if (canvas?.clientWidth) {
        canvas.width = canvas.clientWidth;
        canvas.height = canvas.clientHeight;
      }

      waveformRef.current = {
        audioCtx,
        analyser,
        dataArray: new Uint8Array(analyser.frequencyBinCount),
        history: [],
        maxBars: Math.max(1, Math.floor((canvas?.width ?? 180) / BAR_PITCH_PX)),
        rafId: null,
        lastSampleTime: 0,
        stream,
        ownsStream,
      };
      drawWaveform();
    } catch (e) {
      console.warn("[Waveform] init failed:", e);
    }
  }

  function initSyntheticWaveform() {
    const canvas = canvasRef.current;
    if (canvas?.clientWidth) {
      canvas.width = canvas.clientWidth;
      canvas.height = canvas.clientHeight;
    }
    waveformRef.current = {
      synthetic: true,
      history: [],
      maxBars: Math.max(1, Math.floor((canvas?.width ?? 180) / BAR_PITCH_PX)),
      rafId: null,
      lastSampleTime: 0,
      startTime: performance.now(),
    };
    drawWaveform();
  }

  function teardownWaveform() {
    const s = waveformRef.current;
    if (!s) return;
    if (s.rafId) cancelAnimationFrame(s.rafId);
    if (s.ownsStream && s.stream) {
      s.stream.getTracks().forEach((track) => track.stop());
    }
    try {
      if (s.audioCtx && s.audioCtx.state !== "closed") s.audioCtx.close();
    } catch {
      // already closed
    }
    waveformRef.current = null;
  }

  function resetMicUi() {
    recordingModeRef.current = null;
    discardRef.current = false;
    teardownWaveform();
    setState("idle");
  }

  function stopRecording() {
    if (recordingModeRef.current === "fallback" && recorderRef.current && recorderRef.current.state !== "inactive") {
      teardownWaveform();
      setState("processing");
      try {
        recorderRef.current.stop();
      } catch {
        // already stopped
      }
      return;
    }

    const awaitingResult = !!recognitionRef.current;
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // already stopped
      }
      recognitionRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    recorderRef.current = null;
    chunksRef.current = [];
    mimeTypeRef.current = "";

    if (!awaitingResult) {
      resetMicUi();
      return;
    }
    teardownWaveform();
    setState("processing");
  }

  function discardRecording() {
    if (recordingModeRef.current === "fallback" && recorderRef.current && recorderRef.current.state !== "inactive") {
      discardRef.current = true;
      try {
        recorderRef.current.stop();
      } catch {
        // already stopped
      }
      return;
    }
    if (recognitionRef.current) {
      discardRef.current = true;
      try {
        recognitionRef.current.abort?.() ?? recognitionRef.current.stop();
      } catch {
        // already stopped
      }
      return;
    }
    resetMicUi();
  }

  async function transcribeFallbackChunks() {
    if (!chunksRef.current.length) {
      onToast(lang === "zh-HK" ? "🎤 聽唔到語音。請再試一次。" : "🎤 No speech captured. Please try again.");
      return;
    }
    try {
      const recordedBlob = new Blob(chunksRef.current, { type: mimeTypeRef.current || "audio/webm" });
      const wavBlob = await convertRecordedBlobToWav(recordedBlob);
      const text = await transcribeAudio(wavBlob, lang);
      if (!text) {
        onToast(lang === "zh-HK" ? "🎤 聽唔到語音。請講得清楚啲。" : "🎤 No speech recognized. Please speak clearly.");
        return;
      }
      onTranscript(text);
    } catch (e) {
      console.error("[STT fallback] error:", e);
      onToast(
        lang === "zh-HK"
          ? "⚠️ 語音轉文字暫時失敗，請檢查網絡後再試。"
          : "⚠️ Speech-to-text failed. Please check your network and try again."
      );
    }
  }

  async function startFallbackRecording() {
    if (!navigator.mediaDevices?.getUserMedia) {
      onToast(
        lang === "zh-HK"
          ? "你嘅瀏覽器唔支援錄音。請用 Chrome、Edge 或 Safari。"
          : "Your browser does not support recording. Please use Chrome, Edge, or Safari."
      );
      stopRecording();
      return;
    }
    const mimeCandidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      initWaveformAnalyser(stream, false);
      // `in` rather than a truthiness check on the method: the original JS
      // guarded against old browsers without isTypeSupported, but TS knows
      // the method is always defined on the type and flags the truthiness
      // test as a mistake.
      const canCheckMime = typeof MediaRecorder !== "undefined" && "isTypeSupported" in MediaRecorder;
      mimeTypeRef.current = canCheckMime ? mimeCandidates.find((t) => MediaRecorder.isTypeSupported(t)) || "" : "";
      const recorder = mimeTypeRef.current ? new MediaRecorder(stream, { mimeType: mimeTypeRef.current }) : new MediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];
      recordingModeRef.current = "fallback";

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        }
        if (!discardRef.current) {
          await transcribeFallbackChunks();
        }
        recorderRef.current = null;
        chunksRef.current = [];
        mimeTypeRef.current = "";
        resetMicUi();
      };
      recorder.start(200);
    } catch (e) {
      console.error("[STT fallback] start error:", e);
      onToast(lang === "zh-HK" ? "❌ 無法啟動麥克風，請檢查權限。" : "❌ Unable to start microphone. Please check permissions.");
      stopRecording();
    }
  }

  async function startRecording() {
    discardRef.current = false;
    setState("recording");

    const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognitionCtor) {
      recordingModeRef.current = "webspeech";
      initSyntheticWaveform();
      const recognition = new SpeechRecognitionCtor();
      recognition.lang = lang === "zh-HK" ? "zh-HK" : "en-US";
      recognition.interimResults = false;
      recognition.continuous = false;

      recognition.addEventListener("result", (event: SpeechRecognitionEvent) => {
        const text = event.results[0][0].transcript;
        if (text) onTranscript(text);
      });
      recognition.addEventListener("end", () => {
        resetMicUi();
      });
      recognition.addEventListener("error", () => {
        onToast(lang === "zh-HK" ? "⚠️ 語音辨識發生錯誤。" : "⚠️ A speech recognition error occurred.");
      });

      try {
        recognition.start();
      } catch (e) {
        console.error("[STT] failed to start:", e);
        recognitionRef.current = null;
        stopRecording();
        onToast(lang === "zh-HK" ? "⚠️ 語音功能啟動失敗。" : "⚠️ Failed to start voice recognition.");
        return;
      }
      recognitionRef.current = recognition;
      return;
    }
    await startFallbackRecording();
  }

  useEffect(() => {
    return () => {
      teardownWaveform();
      recognitionRef.current?.stop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <canvas ref={canvasRef} id="voiceWaveform" className={`voice-waveform${micState === "idle" ? " d-none" : ""}`} width={180} height={40} />
      {micState !== "idle" && (
        <button type="button" className="send_btn delete-btn" onClick={discardRecording} title="Discard recording">
          <i className="fas fa-trash" />
        </button>
      )}
      {micState === "recording" ? (
        <button type="button" className="send_btn mic-btn recording-active pulse-recording" onClick={stopRecording} title="Stop">
          <i className="fas fa-stop" />
        </button>
      ) : micState === "processing" ? (
        <button type="button" className="send_btn stop-btn" disabled title="Processing">
          <i className="fas fa-play" />
        </button>
      ) : (
        <button type="button" className="send_btn mic-btn" onClick={startRecording} title="Start Voice">
          <i className="fas fa-microphone" />
        </button>
      )}
    </>
  );
}
