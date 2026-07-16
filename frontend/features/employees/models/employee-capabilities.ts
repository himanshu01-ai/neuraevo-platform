import {
  Bell,
  Brain,
  Calendar,
  Code,
  Folder,
  Github,
  Globe,
  Mail,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import {
  EMPLOYEE_CAPABILITIES,
  type CapabilityAvailability,
  type EmployeeCapability,
} from "@/services/employees";
import { CAPABILITY_LABEL } from "@/types/domain";

/**
 * What each capability is, how it looks, and what will be configurable once the
 * platform can run it.
 *
 * The six executable capabilities take their labels from `CAPABILITY_LABEL` in
 * types/domain.ts rather than restating them — that table mirrors the backend
 * and stays the source. The three platform grants have no backend label, so
 * they are named here.
 */

export interface CapabilityMeta {
  capability: EmployeeCapability;
  label: string;
  description: string;
  icon: LucideIcon;
  /**
   * What you'll be able to set once execution lands. Shown as the capability's
   * future configuration — a promise about scope, not a control.
   */
  futureConfiguration: string;
}

export const CAPABILITY_META: Record<EmployeeCapability, CapabilityMeta> = {
  browser: {
    capability: "browser",
    label: CAPABILITY_LABEL.browser,
    description: "Reads the web and acts on pages.",
    icon: Globe,
    futureConfiguration: "Allowed domains and how many pages a run may open.",
  },
  python: {
    capability: "python",
    label: CAPABILITY_LABEL.python,
    description: "Computes with code in a sandbox.",
    icon: Code,
    futureConfiguration: "Runtime limits and the packages a sandbox may import.",
  },
  files: {
    capability: "files",
    label: CAPABILITY_LABEL.files,
    description: "Reads and writes documents.",
    icon: Folder,
    futureConfiguration: "Which folders are readable, and which are writable.",
  },
  email: {
    capability: "email",
    label: CAPABILITY_LABEL.email,
    description: "Reads the inbox and drafts replies.",
    icon: Mail,
    futureConfiguration: "The mailbox to work from and who may be written to.",
  },
  calendar: {
    capability: "calendar",
    label: CAPABILITY_LABEL.calendar,
    description: "Reads and schedules events.",
    icon: Calendar,
    futureConfiguration: "Which calendars are visible and what hours are bookable.",
  },
  github: {
    capability: "github",
    label: CAPABILITY_LABEL.github,
    description: "Works with a repository.",
    icon: Github,
    futureConfiguration: "The repositories in scope and whether it may push.",
  },
  memory: {
    capability: "memory",
    label: "Memory",
    description: "Recalls and stores what it learns.",
    icon: Brain,
    futureConfiguration: "Which memory categories it may read and add to.",
  },
  approval: {
    capability: "approval",
    label: "Approval",
    description: "Pauses for a human decision.",
    icon: ShieldCheck,
    futureConfiguration: "Who approves, and what can't proceed without them.",
  },
  notification: {
    capability: "notification",
    label: "Notification",
    description: "Tells you when something needs you.",
    icon: Bell,
    futureConfiguration: "The channel to reach you on and what's worth interrupting for.",
  },
};

/** Every capability in canonical order — the six, then the platform grants. */
export const CAPABILITY_LIST: readonly CapabilityMeta[] = EMPLOYEE_CAPABILITIES.map(
  (capability) => CAPABILITY_META[capability]
);

export const AVAILABILITY_LABEL: Record<CapabilityAvailability, string> = {
  GENERAL: "Available",
  PREVIEW: "In preview",
  COMING_SOON: "Coming soon",
};

/**
 * Availability is a fact about the platform, not a status of the employee, so it
 * renders as a plain outline pill rather than a toned one — reserving the status
 * colours for status.
 */
export const AVAILABILITY_DESCRIPTION: Record<CapabilityAvailability, string> = {
  GENERAL: "Ready to use once execution is wired up.",
  PREVIEW: "Shipping behind the platform's own rollout.",
  COMING_SOON: "Planned; not offered yet.",
};
