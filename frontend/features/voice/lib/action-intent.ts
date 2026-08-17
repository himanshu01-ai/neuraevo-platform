/**
 * Action intent — deciding when a turn needs the user's confirmation (Sprint 22).
 *
 * The assistant should never take an outward-facing action (sending a message,
 * scheduling something, running work) without an explicit yes. This pure module
 * reads the user's utterance and recognises when an action is being asked for,
 * so the orchestrator can raise an approval card before proceeding. It performs
 * no action itself — it only classifies intent.
 *
 * Two categories matter:
 *
 * - `executable` — something the platform can actually carry out through an
 *   existing engine (running a workflow or a task). These plug into the
 *   orchestrator's executor seam.
 * - `external` — an outward action (email, message, schedule) whose real
 *   capability isn't wired into the conversation path yet. The assistant still
 *   asks permission and acknowledges conversationally; it does not fabricate a
 *   side effect. This keeps the confirmation honest.
 *
 * Detection is a deliberately simple, transparent keyword scan — not an intent
 * model. It errs toward *asking*: a false positive costs one confirmation tap; a
 * false negative would let an action through unconfirmed, which must not happen.
 */

export type ActionKind =
  | "send_email"
  | "send_message"
  | "schedule"
  | "run_workflow"
  | "run_task"
  | "create_task";

export type ActionCategory = "external" | "executable";

export interface PendingAction {
  kind: ActionKind;
  category: ActionCategory;
  /** Title for the approval card, e.g. "Send email". */
  label: string;
  /** One line paraphrasing what was asked, drawn from the utterance. */
  summary: string;
  /** Why confirmation is required — the assistant explains this aloud. */
  reason: string;
}

interface Rule {
  kind: ActionKind;
  category: ActionCategory;
  label: string;
  reason: string;
  /** Every trigger is a word-boundary match, case-insensitive. */
  triggers: readonly string[];
}

const RULES: readonly Rule[] = [
  {
    kind: "send_email",
    category: "external",
    label: "Send email",
    reason: "Sending an email leaves the workspace, so it needs your confirmation first.",
    triggers: ["email", "e-mail"],
  },
  {
    kind: "send_message",
    category: "external",
    label: "Send message",
    reason: "Sending a message on your behalf needs your confirmation first.",
    triggers: ["message", "text", "dm", "slack", "notify"],
  },
  {
    kind: "schedule",
    category: "external",
    label: "Schedule",
    reason: "Putting something on a calendar needs your confirmation first.",
    triggers: ["schedule", "book", "calendar", "meeting", "invite"],
  },
  {
    kind: "run_workflow",
    category: "executable",
    label: "Run workflow",
    reason: "Running a workflow starts real work, so it needs your confirmation.",
    triggers: ["workflow"],
  },
  {
    kind: "run_task",
    category: "executable",
    label: "Run task",
    reason: "Running a task starts real work, so it needs your confirmation.",
    triggers: ["execute", "run the task"],
  },
  {
    kind: "create_task",
    category: "executable",
    label: "Create task",
    reason: "Creating a task adds it to your workspace, so it's worth confirming.",
    triggers: ["remind me", "create a task", "add a task", "to-do", "todo"],
  },
];

/** The verbs that make an utterance a request to *do*, not just to *discuss*. */
const ACTION_VERBS = [
  "send",
  "email",
  "message",
  "schedule",
  "book",
  "run",
  "execute",
  "create",
  "remind",
  "add",
  "notify",
  "invite",
];

function containsWord(haystack: string, needle: string): boolean {
  // Word-boundary match so "email" doesn't fire inside "emailing a" false-positives
  // are fine, but "themed" must not match "them".
  const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`, "i").test(haystack);
}

/** Trim to a single tidy line for the approval card's summary. */
function toSummary(utterance: string): string {
  const line = utterance.trim().replace(/\s+/g, " ");
  return line.length > 140 ? `${line.slice(0, 139).trimEnd()}…` : line;
}

/**
 * Classify the user's utterance. Returns a `PendingAction` when it reads as an
 * action request, or `null` when it's a plain question or statement (which flows
 * straight to a reply). The first matching rule wins, in declaration order, so
 * the more specific external actions take precedence over the generic ones.
 */
export function detectAction(utterance: string): PendingAction | null {
  const text = utterance.toLowerCase();

  const hasActionVerb = ACTION_VERBS.some((verb) => containsWord(text, verb));
  if (!hasActionVerb) return null;

  for (const rule of RULES) {
    if (rule.triggers.some((trigger) => containsWord(text, trigger))) {
      return {
        kind: rule.kind,
        category: rule.category,
        label: rule.label,
        summary: toSummary(utterance),
        reason: rule.reason,
      };
    }
  }
  return null;
}
