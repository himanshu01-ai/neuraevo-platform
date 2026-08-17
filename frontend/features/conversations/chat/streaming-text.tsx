"use client";

import { useEffect, useState } from "react";
import { useReducedMotion } from "framer-motion";

export interface StreamingTextProps {
  text: string;
  /** Fires once the full text is on screen. */
  onDone?: () => void;
  className?: string;
}

/** Words revealed per tick. Fast enough to feel live, slow enough to read. */
const WORDS_PER_TICK = 2;
const TICK_MS = 60;

/**
 * Reveals a message word by word — the streaming *animation*, and only that.
 * The full text is already in the cache before this mounts; nothing arrives
 * incrementally. Under prefers-reduced-motion the text appears whole,
 * immediately.
 *
 * The full text also renders invisibly to reserve the bubble's final height,
 * so the thread doesn't grow line by line under the reader.
 */
export function StreamingText({ text, onDone, className }: StreamingTextProps) {
  const reducedMotion = useReducedMotion();
  const words = text.split(" ");
  const [shown, setShown] = useState(reducedMotion ? words.length : 0);

  useEffect(() => {
    if (reducedMotion) {
      setShown(words.length);
      onDone?.();
      return;
    }
    if (shown >= words.length) {
      onDone?.();
      return;
    }
    const timer = setTimeout(() => setShown((n) => Math.min(n + WORDS_PER_TICK, words.length)), TICK_MS);
    return () => clearTimeout(timer);
  }, [shown, words.length, reducedMotion, onDone]);

  return (
    <span className={className} aria-live="polite">
      <span aria-hidden="true" className="invisible block h-0 overflow-hidden">
        {text}
      </span>
      {words.slice(0, shown).join(" ")}
      {shown < words.length ? (
        <span aria-hidden="true" className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse rounded-full bg-primary align-middle" />
      ) : null}
    </span>
  );
}
