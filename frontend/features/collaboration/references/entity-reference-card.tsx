"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import type { RelatedEntity } from "@/services/collaboration";
import { ENTITY_META } from "../models/notification-meta";
import { cn } from "@/lib/utils";

/**
 * A platform record referenced from a notification or activity — employee,
 * workflow, task, memory, or conversation — as one card shape. Each links into
 * the module that owns the record; the card carries identity only, the same
 * rule the conversation thread's reference card follows. This is the
 * collaboration-wide reference card the inspector and feed rows reuse rather
 * than duplicating per entity kind.
 */

function resolve(entity: RelatedEntity): { title: string; subtitle: string | null; href: string } {
  switch (entity.kind) {
    case "employee":
      return {
        title: entity.employee.employeeName,
        subtitle: entity.employee.roleTitle,
        href: `/workspace/employees/${entity.employee.employeeId}`,
      };
    case "workflow":
      return {
        title: entity.workflow.workflowName,
        subtitle: null,
        href: `/workspace/workflows/${entity.workflow.workflowId}`,
      };
    case "task":
      return {
        title: entity.task.taskName,
        subtitle: entity.task.businessId,
        href: `/workspace/tasks/${entity.task.taskId}`,
      };
    case "memory":
      return {
        title: entity.memory.title,
        subtitle: null,
        href: `/workspace/memory/${entity.memory.memoryId}`,
      };
    case "conversation":
      return {
        title: entity.conversation.title,
        subtitle: `with ${entity.conversation.employeeName}`,
        href: `/workspace/conversations/${entity.conversation.conversationId}`,
      };
  }
}

export function EntityReferenceCard({ entity, className }: { entity: RelatedEntity; className?: string }) {
  const meta = ENTITY_META[entity.kind];
  const Icon = meta.icon;
  const { title, subtitle, href } = resolve(entity);

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
        <span className="block truncate text-xs text-muted-foreground">
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

/** The compact inline form for a feed row's entity chip. */
export function EntityChip({ entity, className }: { entity: RelatedEntity; className?: string }) {
  const meta = ENTITY_META[entity.kind];
  const Icon = meta.icon;
  const { title } = resolve(entity);

  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1 rounded-full border bg-background px-2 py-0.5 text-xs text-muted-foreground",
        className
      )}
    >
      <Icon className="size-3 shrink-0" aria-hidden="true" />
      <span className="sr-only">{meta.label}: </span>
      <span className="truncate">{title}</span>
    </span>
  );
}
