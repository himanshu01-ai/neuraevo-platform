"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Browser speech, at the edge (Sprint 21).
 *
 * Voice is an interface, not a platform: the microphone, speech-to-text, and
 * text-to-speech all live here in the browser, via the Web Speech API. The
 * platform only ever sees the transcript (as an ordinary message with
 * `channel=voice`) and the reply text (which the browser speaks). No audio is
 * uploaded, stored, or processed server-side.
 *
 * Both hooks degrade gracefully: where the API is missing (`supported === false`)
 * the UI keeps its typed path and simply disables the voice control, with a note
 * saying why. Nothing here does wake-word, VAD, barge-in, or any of the
 * out-of-scope audio work — just dictation in and synthesis out.
 */

// --- Minimal Web Speech API typings (absent from the standard lib.dom) ---

interface SpeechRecognitionAlternativeLike {
  readonly transcript: string;
}

interface SpeechRecognitionResultLike {
  readonly isFinal: boolean;
  readonly length: number;
  readonly [index: number]: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionResultListLike {
  readonly length: number;
  readonly [index: number]: SpeechRecognitionResultLike;
}

interface SpeechRecognitionEventLike {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultListLike;
}

interface SpeechRecognitionErrorEventLike {
  readonly error: string;
}

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

// --- Speech-to-text (microphone → transcript) ---------------------------

export interface SpeechInput {
  /** Whether the browser can transcribe speech at all. */
  supported: boolean;
  /** True while the microphone is open and transcribing. */
  listening: boolean;
  /** The accumulated transcript (final + interim), trimmed. */
  transcript: string;
  /** A human-readable recognition error, or `null`. */
  error: string | null;
  start: () => void;
  stop: () => void;
  reset: () => void;
}

export function useSpeechInput(lang = "en-US"): SpeechInput {
  const ctorRef = useRef<SpeechRecognitionCtor | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const finalRef = useRef("");
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctor = getRecognitionCtor();
    ctorRef.current = ctor;
    setSupported(ctor !== null);
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  const start = useCallback(() => {
    const ctor = ctorRef.current;
    if (!ctor) return;
    setError(null);
    finalRef.current = "";
    setTranscript("");

    const recognition = new ctor();
    recognition.lang = lang;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (!result) continue;
        const text = result[0]?.transcript ?? "";
        if (result.isFinal) finalRef.current += text;
        else interim += text;
      }
      setTranscript(`${finalRef.current}${interim}`.trim());
    };
    recognition.onerror = (event) => {
      // "no-speech"/"aborted" are ordinary stops, not failures worth surfacing.
      if (event.error !== "no-speech" && event.error !== "aborted") {
        setError(
          event.error === "not-allowed"
            ? "Microphone access was blocked."
            : "Speech couldn't be recognised."
        );
      }
      setListening(false);
    };
    recognition.onend = () => setListening(false);

    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }, [lang]);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setListening(false);
  }, []);

  const reset = useCallback(() => {
    finalRef.current = "";
    setTranscript("");
    setError(null);
  }, []);

  return { supported, listening, transcript, error, start, stop, reset };
}

// --- Text-to-speech (reply → spoken) ------------------------------------

export interface SpeechOutput {
  /** Whether the browser can synthesise speech at all. */
  supported: boolean;
  /** True while an utterance is being spoken. */
  speaking: boolean;
  /** The id of the message currently being spoken, or `null`. */
  speakingId: string | null;
  /** Speak ``text``; ``id`` tags which message it belongs to. */
  speak: (text: string, id?: string) => void;
  cancel: () => void;
}

export function useSpeechOutput(): SpeechOutput {
  const [supported, setSupported] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [speakingId, setSpeakingId] = useState<string | null>(null);

  useEffect(() => {
    const has = typeof window !== "undefined" && "speechSynthesis" in window;
    setSupported(has);
    return () => {
      if (has) window.speechSynthesis.cancel();
    };
  }, []);

  const speak = useCallback((text: string, id?: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const trimmed = text.trim();
    if (!trimmed) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(trimmed);
    utterance.onstart = () => {
      setSpeaking(true);
      setSpeakingId(id ?? null);
    };
    const done = () => {
      setSpeaking(false);
      setSpeakingId(null);
    };
    utterance.onend = done;
    utterance.onerror = done;
    window.speechSynthesis.speak(utterance);
  }, []);

  const cancel = useCallback(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    setSpeaking(false);
    setSpeakingId(null);
  }, []);

  return { supported, speaking, speakingId, speak, cancel };
}
