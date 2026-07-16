import { Blocks, Bot, CircleCheck, ShieldCheck, UserPlus, Workflow, type LucideIcon } from "lucide-react";
import type { WorkspaceSignals } from "@/services/dashboard";

export interface SuggestionRule {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
  href: string;
  /** Deterministic predicate over platform signals. No AI, no scoring, no ranking. */
  appliesTo: (signals: WorkspaceSignals) => boolean;
}

/**
 * The suggestion catalog. Each rule is a plain predicate over
 * `WorkspaceSignals` — a recommendation appears because a fact is true, never
 * because a model generated it. Declaration order is the priority order.
 */
export const SUGGESTION_RULES: readonly SuggestionRule[] = [
  {
    id: "complete-onboarding",
    title: "Complete onboarding",
    description: "Finish setting up your workspace so your AI employee has what it needs.",
    icon: CircleCheck,
    href: "/onboarding",
    appliesTo: (signals) => !signals.hasCompletedOnboarding,
  },
  {
    id: "create-first-workflow",
    title: "Create your first workflow",
    description: "Turn work you repeat into a workflow your AI employee can run.",
    icon: Workflow,
    href: "/workspace/workflows",
    appliesTo: (signals) => signals.workflowCount === 0,
  },
  {
    id: "review-approvals",
    title: "Review pending approvals",
    description: "Work is waiting on your decision before it can continue.",
    icon: ShieldCheck,
    href: "/workspace/approvals",
    appliesTo: (signals) => signals.pendingApprovals > 0,
  },
  {
    id: "connect-integrations",
    title: "Connect your integrations",
    description: "Give your AI employee access to the tools you already work in.",
    icon: Blocks,
    href: "/workspace/integrations",
    appliesTo: (signals) => signals.integrationCount === 0,
  },
  {
    id: "customize-employee",
    title: "Customize your AI employee",
    description: "Tune its role and instructions so its work sounds like yours.",
    icon: Bot,
    href: "/workspace/ai-employees",
    appliesTo: (signals) => !signals.hasCustomizedEmployee,
  },
  {
    id: "invite-team",
    title: "Invite your team",
    description: "Bring teammates in to share workflows and approvals.",
    icon: UserPlus,
    href: "/workspace/settings",
    appliesTo: (signals) => signals.teamSize <= 1,
  },
];

/** Every rule whose predicate matches, in catalog order, capped at `limit`. */
export function selectSuggestions(signals: WorkspaceSignals, limit = 3): SuggestionRule[] {
  return SUGGESTION_RULES.filter((rule) => rule.appliesTo(signals)).slice(0, limit);
}
