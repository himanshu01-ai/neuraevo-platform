/**
 * Interaction modes — the four ways in and out of a voice session (Sprint 22).
 *
 * Input and output are independent channels, so the user can, for example, keep
 * speaking while turning spoken replies off (voice-in, text-out) in a quiet
 * room. Pure: these helpers describe the mode; the orchestrator acts on them.
 *
 *   Voice → Voice   speak, hear replies      (the default, hands-free)
 *   Voice → Text    speak, read replies      (quiet room)
 *   Text  → Voice   type, hear replies       (noisy room, eyes-free reply)
 *   Text  → Text    type, read replies       (fully silent — the fallback)
 */

export type ChannelMode = "voice" | "text";

export interface InteractionMode {
  input: ChannelMode;
  output: ChannelMode;
}

export const DEFAULT_INTERACTION_MODE: InteractionMode = {
  input: "voice",
  output: "voice",
};

/** The fully-silent fallback, used when speech is unavailable in the browser. */
export const SILENT_INTERACTION_MODE: InteractionMode = {
  input: "text",
  output: "text",
};

/** Reply out loud only when the output channel is voice. */
export function shouldSpeakReplies(mode: InteractionMode): boolean {
  return mode.output === "voice";
}

/** Reopen the microphone after a turn only when the input channel is voice. */
export function shouldAutoListen(mode: InteractionMode): boolean {
  return mode.input === "voice";
}

/** The message channel a turn should be tagged with, from the input mode. */
export function channelForMode(mode: InteractionMode): ChannelMode {
  return mode.input;
}

/** A short label for the current mode, e.g. "Voice → Text". */
export function describeMode(mode: InteractionMode): string {
  const cap = (c: ChannelMode) => (c === "voice" ? "Voice" : "Text");
  return `${cap(mode.input)} → ${cap(mode.output)}`;
}

/**
 * Reconcile a desired mode against what the browser can actually do. Speech
 * input/output each fall back to text when unsupported, so the experience never
 * offers a channel it can't honour — the core of the voice-disabled fallback.
 */
export function resolveMode(
  desired: InteractionMode,
  capabilities: { speechInput: boolean; speechOutput: boolean }
): InteractionMode {
  return {
    input: capabilities.speechInput ? desired.input : "text",
    output: capabilities.speechOutput ? desired.output : "text",
  };
}
