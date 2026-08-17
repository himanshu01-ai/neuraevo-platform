import {
  Archive,
  ArrowRightLeft,
  Bell,
  BellOff,
  Bookmark,
  Bot,
  Brain,
  CheckCheck,
  CircleCheck,
  CircleX,
  Eye,
  ListChecks,
  MailOpen,
  MessagesSquare,
  Pencil,
  Pin,
  Plus,
  ShieldCheck,
  UserPlus,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import type {
  ActivityKind,
  EntityKind,
  NotificationAction,
  NotificationType,
} from "@/services/collaboration";
import type { StatusTone } from "@/types/domain";

/**
 * Presentation vocabulary for collaboration: an icon per notification type,
 * activity kind, entity kind, and quick action. UI concern only — the service
 * layer names the kinds, this file says how each one looks. Declared once so a
 * feed row, an inspector card, and a nav badge never disagree about what a
 * workflow looks like.
 */

export const NOTIFICATION_TYPE_ICON: Record<NotificationType, LucideIcon> = {
  task: ListChecks,
  workflow: Workflow,
  memory: Brain,
  conversation: MessagesSquare,
  approval: ShieldCheck,
  employee: Bot,
  system: Bell,
};

export const ACTIVITY_KIND_ICON: Record<ActivityKind, LucideIcon> = {
  created: Plus,
  updated: Pencil,
  assigned: UserPlus,
  completed: CircleCheck,
  commented: MessagesSquare,
  mentioned: Bell,
  approved: CircleCheck,
  rejected: CircleX,
  archived: Archive,
};

/** The module an entity belongs to → its icon and the workspace it links into. */
export const ENTITY_META: Record<EntityKind, { icon: LucideIcon; label: string }> = {
  employee: { icon: Bot, label: "AI employee" },
  workflow: { icon: Workflow, label: "Workflow" },
  task: { icon: ListChecks, label: "Task" },
  memory: { icon: Brain, label: "Memory" },
  conversation: { icon: MessagesSquare, label: "Conversation" },
};

export interface QuickActionMeta {
  label: string;
  /** The verb when the action is currently *off* (about to turn on). */
  icon: LucideIcon;
  /** The verb when the action is currently *on* (about to turn off). */
  activeIcon: LucideIcon;
  activeLabel: string;
}

/**
 * Every quick action, with both faces of a toggle. `mark_read` and `archive`
 * read as verbs on the current state; the collaboration toggles carry an
 * on/off pair so the button says what a click will do.
 */
export const QUICK_ACTION_META: Record<NotificationAction, QuickActionMeta> = {
  mark_read: { label: "Mark read", icon: MailOpen, activeIcon: MailOpen, activeLabel: "Mark unread" },
  archive: { label: "Archive", icon: Archive, activeIcon: ArrowRightLeft, activeLabel: "Restore" },
  pin: { label: "Pin", icon: Pin, activeIcon: Pin, activeLabel: "Unpin" },
  bookmark: { label: "Bookmark", icon: Bookmark, activeIcon: Bookmark, activeLabel: "Remove bookmark" },
  follow: { label: "Follow", icon: Eye, activeIcon: Eye, activeLabel: "Unfollow" },
  mute: { label: "Mute", icon: BellOff, activeIcon: Bell, activeLabel: "Unmute" },
};

export const MARK_ALL_READ_ICON: LucideIcon = CheckCheck;

/**
 * Tone → the tinted icon-badge classes a feed row and inspector use. Written
 * out in full because Tailwind extracts class names statically — a computed
 * `bg-${tone}/10` would be purged from the build.
 */
export const TONE_SURFACE: Record<StatusTone, string> = {
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  danger: "bg-destructive/10 text-destructive",
  info: "bg-info/10 text-info",
  neutral: "bg-muted text-muted-foreground",
};
