import {
  Home,
  LayoutDashboard,
  ListChecks,
  Bot,
  Brain,
  ShieldCheck,
  Workflow,
  BarChart3,
  Blocks,
  Bell,
  Settings,
  CircleHelp,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  id: string;
  label: string;
  href: string;
  icon: LucideIcon;
}

export interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
}

/** Primary sidebar sections, grouped. Order is canonical across all nav surfaces. */
export const NAV_GROUPS: NavGroup[] = [
  {
    id: "workspace",
    label: "Workspace",
    items: [
      { id: "home", label: "Home", href: "/workspace", icon: Home },
      { id: "canvas", label: "Workspace", href: "/workspace/canvas", icon: LayoutDashboard },
      { id: "tasks", label: "Tasks", href: "/workspace/tasks", icon: ListChecks },
      { id: "employees", label: "AI Employees", href: "/workspace/employees", icon: Bot },
    ],
  },
  {
    id: "automation",
    label: "Automation",
    items: [
      { id: "workflows", label: "Workflows", href: "/workspace/workflows", icon: Workflow },
      { id: "approvals", label: "Approvals", href: "/workspace/approvals", icon: ShieldCheck },
      { id: "memory", label: "Memory", href: "/workspace/memory", icon: Brain },
    ],
  },
  {
    id: "insights",
    label: "Insights",
    items: [
      { id: "analytics", label: "Analytics", href: "/workspace/analytics", icon: BarChart3 },
      { id: "integrations", label: "Integrations", href: "/workspace/integrations", icon: Blocks },
      { id: "notifications", label: "Notifications", href: "/workspace/notifications", icon: Bell },
    ],
  },
];

/** Pinned to the bottom of the sidebar. */
export const NAV_FOOTER: NavItem[] = [
  { id: "settings", label: "Settings", href: "/workspace/settings", icon: Settings },
  { id: "help", label: "Help", href: "/workspace/help", icon: CircleHelp },
];

/** Flat list of every navigable item. */
export const ALL_NAV_ITEMS: NavItem[] = [...NAV_GROUPS.flatMap((g) => g.items), ...NAV_FOOTER];

/** The four primary destinations surfaced in the mobile bottom bar. */
export const MOBILE_PRIMARY_IDS = ["home", "tasks", "workflows", "approvals"] as const;
