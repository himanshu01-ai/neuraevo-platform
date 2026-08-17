import { describe, expect, it } from "vitest";
import { detectAction } from "./action-intent";

describe("action intent detection", () => {
  it("passes plain questions through without an approval", () => {
    expect(detectAction("What's on my plate this week?")).toBeNull();
    expect(detectAction("Summarise the last standup.")).toBeNull();
    expect(detectAction("Who owns the pricing doc?")).toBeNull();
  });

  it("flags an email as an external action needing confirmation", () => {
    const action = detectAction("Email Himanshu that I'm on leave.");
    expect(action).not.toBeNull();
    expect(action?.kind).toBe("send_email");
    expect(action?.category).toBe("external");
    expect(action?.label).toBe("Send email");
    expect(action?.reason).toMatch(/confirm/i);
  });

  it("carries a tidy summary of the request", () => {
    const action = detectAction("Send a message to the team about the outage.");
    expect(action?.kind).toBe("send_message");
    expect(action?.summary).toBe("Send a message to the team about the outage.");
  });

  it("flags scheduling", () => {
    expect(detectAction("Schedule a meeting with design next week.")?.kind).toBe("schedule");
    expect(detectAction("Book time with Nova tomorrow.")?.kind).toBe("schedule");
  });

  it("recognises executable platform actions", () => {
    expect(detectAction("Run the onboarding workflow.")?.category).toBe("executable");
    expect(detectAction("Remind me to file the report.")?.kind).toBe("create_task");
  });

  it("does not fire on a trigger word without an action verb", () => {
    // "meeting" is a schedule trigger, but with no verb of doing this is a
    // discussion, not a request — so it stays a plain reply.
    expect(detectAction("The meeting notes are thorough.")).toBeNull();
    expect(detectAction("That workflow is elegant.")).toBeNull();
  });

  it("errs toward asking: an action verb + trigger always confirms", () => {
    // A false positive costs one tap; a missed action must never slip through.
    expect(detectAction("Can you send an email later?")).not.toBeNull();
  });

  it("truncates a very long utterance in the summary", () => {
    const long = `Email the whole team ${"and everyone else ".repeat(20)}now.`;
    const action = detectAction(long);
    expect(action).not.toBeNull();
    expect(action!.summary.length).toBeLessThanOrEqual(140);
    expect(action!.summary.endsWith("…")).toBe(true);
  });
});
