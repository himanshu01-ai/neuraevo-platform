import {
  Home,
  ListChecks,
  Bot,
  Brain,
  MessagesSquare,
  AudioLines,
  ShieldCheck,
  Workflow,
  Bell,
  Activity,
  AtSign,
  Users,
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

/**
 * Primary sidebar sections, grouped. Order is canonical across all nav surfaces.
 *
 * Sprint 23 made this a map of destinations that actually exist: Voice — the
 * platform's headline interaction — became a first-class entry, and the
 * placeholder links that only reached a "Coming soon" page (canvas, analytics,
 * integrations, settings, help) were removed so there are no dead ends. What is
 * listed here is reachable and real.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    id: "workspace",
    label: "Workspace",
    items: [
      { id: "home", label: "Home", href: "/workspace", icon: Home },
      { id: "conversations", label: "Conversations", href: "/workspace/conversations", icon: MessagesSquare },
      { id: "voice", label: "Voice", href: "/voice", icon: AudioLines },
      { id: "tasks", label: "Tasks", href: "/workspace/tasks", icon: ListChecks },
      { id: "employees", label: "AI Employees", href: "/workspace/employees", icon: Bot },
    ],
  },
  {
    id: "automation",
    label: "Automation",
    items: [
      { id: "workflows", label: "Workflows", href: "/workspace/workflows", icon: Workflow },
      { id: "approvals", label: "Approvals", href: "/workspace/collaboration/approvals", icon: ShieldCheck },
      { id: "memory", label: "Memory", href: "/workspace/memory", icon: Brain },
    ],
  },
  {
    id: "collaboration",
    label: "Collaboration",
    items: [
      { id: "notifications", label: "Notifications", href: "/workspace/collaboration", icon: Bell },
      { id: "activity", label: "Activity", href: "/workspace/collaboration/activity", icon: Activity },
      { id: "mentions", label: "Mentions", href: "/workspace/collaboration/mentions", icon: AtSign },
      { id: "team", label: "Team activity", href: "/workspace/collaboration/team", icon: Users },
    ],
  },
];

/**
 * Pinned to the bottom of the sidebar. Empty for now: the Settings and Help
 * destinations aren't built yet, and Sprint 23 removed the placeholder links
 * rather than leave them pointing at a "Coming soon" page.
 */
export const NAV_FOOTER: NavItem[] = [];

/** Flat list of every navigable item. */
export const ALL_NAV_ITEMS: NavItem[] = [...NAV_GROUPS.flatMap((g) => g.items), ...NAV_FOOTER];

/** The four primary destinations surfaced in the mobile bottom bar. */
export const MOBILE_PRIMARY_IDS = ["home", "tasks", "workflows", "approvals"] as const;
