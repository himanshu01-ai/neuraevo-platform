import { describe, expect, it } from "vitest";
import {
  DEFAULT_INTERACTION_MODE,
  SILENT_INTERACTION_MODE,
  channelForMode,
  describeMode,
  resolveMode,
  shouldAutoListen,
  shouldSpeakReplies,
} from "./interaction-mode";

describe("interaction modes", () => {
  it("defaults to voice in, voice out", () => {
    expect(DEFAULT_INTERACTION_MODE).toEqual({ input: "voice", output: "voice" });
  });

  it("speaks replies only when output is voice", () => {
    expect(shouldSpeakReplies({ input: "voice", output: "voice" })).toBe(true);
    expect(shouldSpeakReplies({ input: "voice", output: "text" })).toBe(false);
  });

  it("auto-listens only when input is voice", () => {
    expect(shouldAutoListen({ input: "voice", output: "text" })).toBe(true);
    expect(shouldAutoListen({ input: "text", output: "voice" })).toBe(false);
  });

  it("derives the message channel from the input mode", () => {
    expect(channelForMode({ input: "voice", output: "text" })).toBe("voice");
    expect(channelForMode({ input: "text", output: "voice" })).toBe("text");
  });

  it("describes the mode as an arrow", () => {
    expect(describeMode({ input: "voice", output: "text" })).toBe("Voice → Text");
    expect(describeMode(SILENT_INTERACTION_MODE)).toBe("Text → Text");
  });

  it("resolves a mode against browser capabilities (voice-disabled fallback)", () => {
    const desired = { input: "voice", output: "voice" } as const;
    // No speech at all → fully silent.
    expect(resolveMode(desired, { speechInput: false, speechOutput: false })).toEqual(
      SILENT_INTERACTION_MODE
    );
    // Output only → keep hearing, but type.
    expect(resolveMode(desired, { speechInput: false, speechOutput: true })).toEqual({
      input: "text",
      output: "voice",
    });
    // Everything supported → unchanged.
    expect(resolveMode(desired, { speechInput: true, speechOutput: true })).toEqual(desired);
  });
});
