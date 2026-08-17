/**
 * The Voice Session lifecycle — a pure state machine (Sprint 22).
 *
 * A voice session moves through clearly-named phases so the UI (and the orb)
 * can communicate exactly what the assistant is doing. This module is pure: no
 * React, no services, no side effects — just `reduce(state, event) → state`.
 * The orchestrator hook drives it from real signals (the microphone, the turn's
 * async lifecycle, speech synthesis), and it is unit-tested in isolation.
 *
 * The cycle, in the order a turn actually moves:
 *
 *   idle → connecting → listening → understanding → thinking
 *        → (planning → waiting_permission → executing) → speaking
 *        → completed → returning → listening …
 *
 * The bracketed states only occur when a turn needs a confirmed action; a plain
 * question skips straight from thinking to speaking. `returning` exists so the
 * UI can show a brief, calm hand-back before the mic reopens, rather than
 * snapping between speaking and listening.
 */

export const VOICE_STATES = [
  "idle",
  "connecting",
  "listening",
  "understanding",
  "thinking",
  "planning",
  "waiting_permission",
  "executing",
  "speaking",
  "completed",
  "returning",
  "error",
] as const;

export type VoiceState = (typeof VOICE_STATES)[number];

export type VoiceEvent =
  | { type: "CONNECT" }
  | { type: "CONNECTED" }
  | { type: "MIC_OPEN" }
  | { type: "TRANSCRIPT_FINAL" }
  | { type: "THINK" }
  | { type: "PLAN_ACTION" }
  | { type: "APPROVE" }
  | { type: "DENY" }
  | { type: "EXECUTE_DONE" }
  | { type: "SPEAK" }
  | { type: "SPEAK_END" }
  | { type: "CONTINUE" }
  | { type: "STOP" }
  | { type: "ERROR" }
  | { type: "RESET" };

/** Human-readable status line for each state — what the assistant is doing. */
export const VOICE_STATE_LABEL: Record<VoiceState, string> = {
  idle: "Ready when you are",
  connecting: "Connecting…",
  listening: "Listening",
  understanding: "Understanding…",
  thinking: "Thinking…",
  planning: "Planning…",
  waiting_permission: "Waiting for your confirmation",
  executing: "Working on it…",
  speaking: "Speaking",
  completed: "Done",
  returning: "Back to you",
  error: "Something went wrong",
};

/** States in which the assistant is actively working (drives the orb energy). */
export function isBusy(state: VoiceState): boolean {
  return (
    state === "understanding" ||
    state === "thinking" ||
    state === "planning" ||
    state === "executing"
  );
}

/** The microphone should be capturing only while listening. */
export function isMicActive(state: VoiceState): boolean {
  return state === "listening";
}

const TRANSITIONS: Record<VoiceState, Partial<Record<VoiceEvent["type"], VoiceState>>> = {
  idle: { CONNECT: "connecting", MIC_OPEN: "listening", ERROR: "error" },
  connecting: { CONNECTED: "listening", ERROR: "error", STOP: "idle" },
  listening: {
    TRANSCRIPT_FINAL: "understanding",
    STOP: "idle",
    ERROR: "error",
  },
  understanding: { THINK: "thinking", ERROR: "error", STOP: "idle" },
  thinking: {
    PLAN_ACTION: "planning",
    SPEAK: "speaking",
    ERROR: "error",
    STOP: "idle",
  },
  planning: { PLAN_ACTION: "waiting_permission", ERROR: "error", STOP: "idle" },
  waiting_permission: {
    APPROVE: "executing",
    // Declining an action still gets a spoken acknowledgement, not silence.
    DENY: "speaking",
    ERROR: "error",
    STOP: "idle",
  },
  executing: { EXECUTE_DONE: "speaking", ERROR: "error", STOP: "idle" },
  speaking: { SPEAK_END: "completed", STOP: "idle", ERROR: "error" },
  completed: { CONTINUE: "returning", STOP: "idle" },
  // From the hand-back, reopen the mic for a voice turn, or rest at idle.
  returning: { MIC_OPEN: "listening", STOP: "idle", ERROR: "error" },
  error: { RESET: "idle", MIC_OPEN: "listening", STOP: "idle" },
};

/** The initial state of a fresh session. */
export const INITIAL_VOICE_STATE: VoiceState = "idle";

/**
 * Apply an event. Unknown transitions are a no-op (the state is returned
 * unchanged) so a stray signal never corrupts the session — the machine only
 * ever moves along a defined edge.
 */
export function voiceReducer(state: VoiceState, event: VoiceEvent): VoiceState {
  return TRANSITIONS[state][event.type] ?? state;
}

/** Whether an event would change the state — useful to avoid redundant work. */
export function canTransition(state: VoiceState, event: VoiceEvent["type"]): boolean {
  return TRANSITIONS[state][event] !== undefined;
}
