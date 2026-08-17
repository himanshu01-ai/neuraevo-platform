import { Bell, Bot, Brain, Flag, Route, ShieldCheck, Wrench, Workflow, type LucideIcon } from "lucide-react";
import { EXECUTION_NODE_KINDS, type ExecutionNodeKind } from "@/services/tasks";

/**
 * What each node in an execution graph is and how it looks.
 *
 * Node chips are deliberately neutral. Colour in this system carries status, and
 * a node already has one (`NodeStatus`) — tinting by kind as well would spend a
 * semantic signal on a non-semantic distinction and leave two colours arguing on
 * one card. The icon carries the kind instead.
 */

export interface ExecutionNodeMeta {
  kind: ExecutionNodeKind;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const EXECUTION_NODE_META: Record<ExecutionNodeKind, ExecutionNodeMeta> = {
  planning: {
    kind: "planning",
    label: "Planning",
    description: "Works out the steps before anything runs.",
    icon: Route,
  },
  workflow: {
    kind: "workflow",
    label: "Workflow",
    description: "The shape of the job.",
    icon: Workflow,
  },
  employee: {
    kind: "employee",
    label: "AI Employee",
    description: "Who carries the work.",
    icon: Bot,
  },
  capability: {
    kind: "capability",
    label: "Capability",
    description: "What it reached for.",
    icon: Wrench,
  },
  approval: {
    kind: "approval",
    label: "Approval",
    description: "Where it stops for a person.",
    icon: ShieldCheck,
  },
  memory: {
    kind: "memory",
    label: "Memory",
    description: "What it recalled or stored.",
    icon: Brain,
  },
  notification: {
    kind: "notification",
    label: "Notification",
    description: "Who it told.",
    icon: Bell,
  },
  result: {
    kind: "result",
    label: "Result",
    description: "What the run produced.",
    icon: Flag,
  },
};

/** Every node kind in canonical order. */
export const EXECUTION_NODE_LIST: readonly ExecutionNodeMeta[] = EXECUTION_NODE_KINDS.map(
  (kind) => EXECUTION_NODE_META[kind]
);
