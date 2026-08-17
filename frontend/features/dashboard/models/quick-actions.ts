import {
  BarChart3,
  Blocks,
  Bot,
  Brain,
  LayoutTemplate,
  ShieldCheck,
  Upload,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export interface QuickAction {
  id: string;
  label: string;
  icon: LucideIcon;
  href: string;
}

/**
 * The quick-action rail. Every entry is navigation and nothing else — no
 * creation, no mutation, no side effects. A destination that has no screen yet
 * lands on the workspace's coming-soon page via the catch-all route.
 */
export const QUICK_ACTIONS: readonly QuickAction[] = [
  { id: "new-workflow", label: "New workflow", icon: Workflow, href: "/workspace/workflows" },
  { id: "assign-employee", label: "Assign AI employee", icon: Bot, href: "/workspace/ai-employees" },
  { id: "upload-files", label: "Upload files", icon: Upload, href: "/workspace/files" },
  { id: "open-memory", label: "Open memory", icon: Brain, href: "/workspace/memory" },
  { id: "view-approvals", label: "View approvals", icon: ShieldCheck, href: "/workspace/approvals" },
  { id: "browse-templates", label: "Browse templates", icon: LayoutTemplate, href: "/workspace/templates" },
  { id: "open-analytics", label: "Open analytics", icon: BarChart3, href: "/workspace/analytics" },
  { id: "manage-integrations", label: "Manage integrations", icon: Blocks, href: "/workspace/integrations" },
];
