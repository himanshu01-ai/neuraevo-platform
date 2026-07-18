import { Activity, AtSign, Bell, Inbox, ShieldCheck, Users, type LucideIcon } from "lucide-react";
import type { CollaborationCounts } from "@/services/collaboration";

/** Which count, if any, a tab badges itself with. */
export type CountKey = keyof CollaborationCounts | null;

export interface CollaborationTab {
  id: string;
  label: string;
  href: string;
  icon: LucideIcon;
  countKey: CountKey;
}

/**
 * The collaboration workspace's screens, in canonical order. The header renders
 * these as links and badges each with its live count. One source of truth so
 * the header, and any future nav, stay in step.
 */
export const COLLABORATION_TABS: CollaborationTab[] = [
  { id: "center", label: "Notifications", href: "/workspace/collaboration", icon: Bell, countKey: "unread" },
  { id: "inbox", label: "Inbox", href: "/workspace/collaboration/inbox", icon: Inbox, countKey: "unread" },
  { id: "activity", label: "Activity", href: "/workspace/collaboration/activity", icon: Activity, countKey: null },
  { id: "approvals", label: "Approvals", href: "/workspace/collaboration/approvals", icon: ShieldCheck, countKey: "pendingApprovals" },
  { id: "mentions", label: "Mentions", href: "/workspace/collaboration/mentions", icon: AtSign, countKey: "mentions" },
  { id: "team", label: "Team activity", href: "/workspace/collaboration/team", icon: Users, countKey: null },
];
