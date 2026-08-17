import { describe, expect, it } from "vitest";
import {
  INITIAL_VOICE_STATE,
  VOICE_STATES,
  VOICE_STATE_LABEL,
  canTransition,
  isBusy,
  isMicActive,
  voiceReducer,
  type VoiceEvent,
  type VoiceState,
} from "./session-machine";

/** Drive a sequence of events from a starting state. */
function run(from: VoiceState, ...events: VoiceEvent["type"][]): VoiceState {
  return events.reduce(
    (state, type) => voiceReducer(state, { type } as VoiceEvent),
    from
  );
}

describe("voice session machine", () => {
  it("starts idle", () => {
    expect(INITIAL_VOICE_STATE).toBe("idle");
  });

  it("labels every state", () => {
    for (const state of VOICE_STATES) {
      expect(VOICE_STATE_LABEL[state]).toBeTruthy();
    }
  });

  it("runs a plain question: listen → understand → think → speak → done → return → listen", () => {
    expect(
      run(
        "listening",
        "TRANSCRIPT_FINAL",
        "THINK",
        "SPEAK",
        "SPEAK_END",
        "CONTINUE",
        "MIC_OPEN"
      )
    ).toBe("listening");
  });

  it("runs an action turn through the permission gate to execution", () => {
    let s = run("thinking", "PLAN_ACTION"); // → planning
    expect(s).toBe("planning");
    s = voiceReducer(s, { type: "PLAN_ACTION" }); // → waiting_permission
    expect(s).toBe("waiting_permission");
    s = voiceReducer(s, { type: "APPROVE" }); // → executing
    expect(s).toBe("executing");
    s = voiceReducer(s, { type: "EXECUTE_DONE" }); // → speaking
    expect(s).toBe("speaking");
  });

  it("declining an action still speaks an acknowledgement", () => {
    expect(voiceReducer("waiting_permission", { type: "DENY" })).toBe("speaking");
  });

  it("connects before listening", () => {
    expect(run("idle", "CONNECT", "CONNECTED")).toBe("listening");
  });

  it("STOP from any active state returns to idle", () => {
    for (const state of ["listening", "thinking", "speaking", "executing"] as const) {
      expect(voiceReducer(state, { type: "STOP" })).toBe("idle");
    }
  });

  it("ERROR is reachable and recoverable", () => {
    expect(voiceReducer("thinking", { type: "ERROR" })).toBe("error");
    expect(voiceReducer("error", { type: "RESET" })).toBe("idle");
    expect(voiceReducer("error", { type: "MIC_OPEN" })).toBe("listening");
  });

  it("ignores undefined transitions (no corruption from stray signals)", () => {
    // You can't approve while listening, or speak-end while thinking.
    expect(voiceReducer("listening", { type: "APPROVE" })).toBe("listening");
    expect(voiceReducer("thinking", { type: "SPEAK_END" })).toBe("thinking");
    expect(canTransition("listening", "APPROVE")).toBe(false);
    expect(canTransition("thinking", "SPEAK")).toBe(true);
  });

  it("marks busy and mic states correctly", () => {
    expect(isBusy("thinking")).toBe(true);
    expect(isBusy("executing")).toBe(true);
    expect(isBusy("listening")).toBe(false);
    expect(isMicActive("listening")).toBe(true);
    expect(isMicActive("speaking")).toBe(false);
  });
});
