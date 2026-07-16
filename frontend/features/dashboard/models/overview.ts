import { Activity, Bot, Brain, ListChecks, ShieldCheck, Workflow, type LucideIcon } from "lucide-react";
import type { OverviewMetricId } from "@/services/dashboard";

/**
 * Presentation for each overview card. The service supplies the numbers and
 * status; this table supplies the icon, title, and destination. Icons match
 * `features/workspace/navigation/nav-config.ts` so a concept looks the same
 * everywhere in the workspace.
 */
export interface OverviewCardMeta {
  title: string;
  icon: LucideIcon;
  href: string;
  /** Read out to assistive tech in place of the bare number. */
  unit: string;
}

export const OVERVIEW_CARD_META: Record<OverviewMetricId, OverviewCardMeta> = {
  tasks: { title: "Tasks", icon: ListChecks, href: "/workspace/tasks", unit: "tasks" },
  workflows: { title: "Workflows", icon: Workflow, href: "/workspace/workflows", unit: "workflows" },
  employees: { title: "AI Employees", icon: Bot, href: "/workspace/ai-employees", unit: "AI employees" },
  approvals: { title: "Approvals", icon: ShieldCheck, href: "/workspace/approvals", unit: "approvals" },
  memory: { title: "Memory", icon: Brain, href: "/workspace/memory", unit: "memories" },
  health: { title: "Health", icon: Activity, href: "/workspace/analytics", unit: "subsystems" },
};
