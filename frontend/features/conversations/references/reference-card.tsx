"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import type { MemoryRef, TaskRef, WorkflowRef } from "@/services/conversations";
import { MESSAGE_KIND_META } from "../models/message-kinds";
import { cn } from "@/lib/utils";

/**
 * A platform record referenced from a thread — workflow, task, or memory — as
 * one card shape. Each links into the module that owns the record; the card
 * carries identity only, the same rule `TaskWorkflowRef` follows on the board.
 */

export type ReferencePayload =
  | { kind: "workflow"; workflow: WorkflowRef }
  | { kind: "task"; task: TaskRef }
  | { kind: "memory"; memory: MemoryRef };

function resolve(payload: ReferencePayload): {
  meta: (typeof MESSAGE_KIND_META)[keyof typeof MESSAGE_KIND_META];
  title: string;
  /** Extra identity beyond the kind label, when the record has one. */
  subtitle: string | null;
  href: string;
} {
  switch (payload.kind) {
    case "workflow":
      return {
        meta: MESSAGE_KIND_META.workflow_reference,
        title: payload.workflow.workflowName,
        subtitle: null,
        href: `/workspace/workflows/${payload.workflow.workflowId}`,
      };
    case "task":
      return {
        meta: MESSAGE_KIND_META.task_reference,
        title: payload.task.taskName,
        subtitle: payload.task.businessId,
        href: `/workspace/tasks/${payload.task.taskId}`,
      };
    case "memory":
      return {
        meta: MESSAGE_KIND_META.memory_reference,
        title: payload.memory.title,
        subtitle: null,
        href: `/workspace/memory/${payload.memory.memoryId}`,
      };
  }
}

export function ReferenceCard({ payload, className }: { payload: ReferencePayload; className?: string }) {
  const { meta, title, subtitle, href } = resolve(payload);
  const Icon = meta.icon;

  return (
    <Link
      href={href}
      className={cn(
        "group flex items-center gap-3 rounded-lg border bg-card p-3 shadow-sm transition-all",
        "hover:border-primary/30 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className
      )}
    >
      <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{title}</span>
        <span className="block text-xs text-muted-foreground">
          {subtitle ? `${meta.label} · ${subtitle}` : meta.label}
        </span>
      </span>
      <ArrowUpRight
        className="size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary"
        aria-hidden="true"
      />
    </Link>
  );
}
