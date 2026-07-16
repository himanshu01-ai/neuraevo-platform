import {
  Bell,
  Brain,
  Calendar,
  Code,
  FileText,
  Flag,
  GitBranch,
  Github,
  Globe,
  ListChecks,
  Mail,
  Repeat,
  Route,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { NODE_KINDS, type NodeKind } from "@/services/workflows";

/**
 * The step palette: what each node kind is, how it looks, and which properties
 * the inspector lets you edit.
 *
 * Node chips are deliberately neutral. Color in this system carries status
 * (`StatusTone`), so tinting a node by category would spend a semantic signal on
 * a non-semantic distinction — the icon and the library grouping carry category
 * instead.
 */

export const NODE_CATEGORIES = ["Flow", "Capabilities", "Platform"] as const;
export type NodeCategory = (typeof NODE_CATEGORIES)[number];

export interface NodeConfigField {
  key: string;
  label: string;
  control: "text" | "textarea" | "select";
  options?: readonly string[];
  placeholder?: string;
  description?: string;
}

export interface NodeTypeMeta {
  kind: NodeKind;
  label: string;
  description: string;
  icon: LucideIcon;
  category: NodeCategory;
  /** Editable configuration surfaced by the PropertiesPanel. */
  fields: readonly NodeConfigField[];
}

export const NODE_TYPES: Record<NodeKind, NodeTypeMeta> = {
  planning: {
    kind: "planning",
    label: "Planning",
    description: "Break the goal into steps.",
    icon: Route,
    category: "Flow",
    fields: [
      { key: "objective", label: "Objective", control: "textarea", placeholder: "What should be planned?" },
    ],
  },
  task: {
    kind: "task",
    label: "Task",
    description: "Do a unit of work.",
    icon: ListChecks,
    category: "Flow",
    fields: [
      { key: "instruction", label: "Instruction", control: "textarea", placeholder: "What should happen here?" },
    ],
  },
  condition: {
    kind: "condition",
    label: "Condition",
    description: "Branch on a check.",
    icon: GitBranch,
    category: "Flow",
    fields: [
      {
        key: "expression",
        label: "Expression",
        control: "text",
        placeholder: "e.g. checks.passed",
        description: "Evaluated by the platform at run time.",
      },
    ],
  },
  loop: {
    kind: "loop",
    label: "Loop",
    description: "Repeat over a collection.",
    icon: Repeat,
    category: "Flow",
    fields: [
      { key: "collection", label: "Collection", control: "text", placeholder: "e.g. segments" },
      { key: "maxIterations", label: "Max iterations", control: "text", placeholder: "e.g. 10" },
    ],
  },
  output: {
    kind: "output",
    label: "Output",
    description: "Return the result.",
    icon: Flag,
    category: "Flow",
    fields: [{ key: "format", label: "Format", control: "select", options: ["Markdown", "JSON", "Text"] }],
  },
  browser: {
    kind: "browser",
    label: "Browser",
    description: "Read the web.",
    icon: Globe,
    category: "Capabilities",
    fields: [
      { key: "query", label: "Query or URL", control: "text", placeholder: "What to look up" },
      { key: "maxResults", label: "Max results", control: "text", placeholder: "e.g. 10" },
    ],
  },
  python: {
    kind: "python",
    label: "Python",
    description: "Compute with code.",
    icon: Code,
    category: "Capabilities",
    fields: [{ key: "script", label: "Script", control: "textarea", placeholder: "# runs on the platform" }],
  },
  file: {
    kind: "file",
    label: "File",
    description: "Read or write a file.",
    icon: FileText,
    category: "Capabilities",
    fields: [
      { key: "path", label: "Path", control: "text", placeholder: "e.g. reports/q3.csv" },
      { key: "mode", label: "Mode", control: "select", options: ["Read", "Write"] },
    ],
  },
  email: {
    kind: "email",
    label: "Email",
    description: "Read or send mail.",
    icon: Mail,
    category: "Capabilities",
    fields: [
      { key: "folder", label: "Folder", control: "text", placeholder: "e.g. Support" },
      { key: "recipient", label: "Recipient", control: "text", placeholder: "who@company.com" },
      { key: "subject", label: "Subject", control: "text" },
    ],
  },
  calendar: {
    kind: "calendar",
    label: "Calendar",
    description: "Read or schedule events.",
    icon: Calendar,
    category: "Capabilities",
    fields: [
      { key: "calendarId", label: "Calendar", control: "text", placeholder: "e.g. primary" },
      { key: "window", label: "Window", control: "text", placeholder: "e.g. next 7 days" },
    ],
  },
  github: {
    kind: "github",
    label: "GitHub",
    description: "Work with a repository.",
    icon: Github,
    category: "Capabilities",
    fields: [
      { key: "repository", label: "Repository", control: "text", placeholder: "owner/repo" },
      { key: "reference", label: "Reference", control: "text", placeholder: "e.g. main or #42" },
    ],
  },
  approval: {
    kind: "approval",
    label: "Approval",
    description: "Wait for a human decision.",
    icon: ShieldCheck,
    category: "Platform",
    fields: [
      { key: "approver", label: "Approver", control: "text", placeholder: "who@company.com" },
      { key: "reason", label: "Reason", control: "textarea", placeholder: "Why approval is needed" },
    ],
  },
  notification: {
    kind: "notification",
    label: "Notification",
    description: "Tell someone something.",
    icon: Bell,
    category: "Platform",
    fields: [
      { key: "channel", label: "Channel", control: "select", options: ["In-app", "Email"] },
      { key: "message", label: "Message", control: "textarea" },
    ],
  },
  memory: {
    kind: "memory",
    label: "Memory",
    description: "Recall or store what's known.",
    icon: Brain,
    category: "Platform",
    fields: [
      { key: "category", label: "Category", control: "select", options: ["Preferences", "People", "Projects", "Facts"] },
      { key: "query", label: "Query", control: "text", placeholder: "What to recall" },
    ],
  },
};

/** Every node type in canonical order. */
export const NODE_TYPE_LIST: readonly NodeTypeMeta[] = NODE_KINDS.map((kind) => NODE_TYPES[kind]);

/** Node types grouped for the step library, in canonical category order. */
export const NODE_TYPES_BY_CATEGORY: readonly { category: NodeCategory; types: NodeTypeMeta[] }[] =
  NODE_CATEGORIES.map((category) => ({
    category,
    types: NODE_TYPE_LIST.filter((type) => type.category === category),
  }));
