"use client";

import { memo, useState } from "react";
import Link from "next/link";
import { Copy, Ellipsis, Pencil, Settings, Trash2, Workflow as WorkflowIcon } from "lucide-react";
import type { WorkflowSummary } from "@/services/workflows";
import { Button } from "@/components/ui/button";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { StatusBadge } from "@/components/ui/status-badge";

export interface WorkflowCardProps {
  workflow: WorkflowSummary;
  onDuplicate: (id: string) => void;
  onDelete: (id: string) => void;
}

/**
 * One workflow in the list: what it is, how ready it is, and how to open it.
 *
 * Delete asks first, inline. Removing someone's work on a single click of a menu
 * item is not a thing to do, and the confirmation lives here so the list doesn't
 * have to track which card is asking.
 */
export const WorkflowCard = memo(function WorkflowCard({ workflow, onDuplicate, onDelete }: WorkflowCardProps) {
  const [isConfirming, setIsConfirming] = useState(false);

  return (
    <div className="flex flex-col rounded-lg border bg-card p-5 shadow-sm transition-all hover:border-primary/30 hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <span className="inline-flex size-9 items-center justify-center rounded-md bg-primary/10 text-primary">
          <WorkflowIcon className="size-5" aria-hidden="true" />
        </span>
        <div className="flex items-center gap-1.5">
          <StatusBadge kind="workflow" status={workflow.status} />
          <DropdownMenu
            menuLabel={`Actions for ${workflow.name}`}
            align="end"
            items={[
              {
                key: "edit",
                label: "Open in builder",
                icon: Pencil,
                href: `/workspace/workflows/${workflow.id}/builder`,
              },
              {
                key: "settings",
                label: "Settings",
                icon: Settings,
                href: `/workspace/workflows/${workflow.id}/settings`,
              },
              { key: "duplicate", label: "Duplicate", icon: Copy, onSelect: () => onDuplicate(workflow.id) },
              {
                key: "delete",
                label: "Delete",
                icon: Trash2,
                destructive: true,
                onSelect: () => setIsConfirming(true),
              },
            ]}
            renderTrigger={(props) => (
              <Button
                {...props}
                variant="ghost"
                size="icon"
                className="size-7 text-muted-foreground"
                aria-label={`Actions for ${workflow.name}`}
              >
                <Ellipsis className="size-4" aria-hidden="true" />
              </Button>
            )}
          />
        </div>
      </div>

      {/* A plain link, not a stretched one: the card holds a menu button, and an
          overlay link would swallow its clicks. */}
      <h3 className="mt-4 text-sm font-semibold">
        <Link
          href={`/workspace/workflows/${workflow.id}`}
          className="rounded-sm text-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {workflow.name}
        </Link>
      </h3>
      <p className="mt-1 line-clamp-2 flex-1 text-sm text-muted-foreground">{workflow.description}</p>

      {isConfirming ? (
        <div role="alert" className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 p-2.5">
          <p className="text-xs text-destructive">Delete “{workflow.name}”? This can't be undone.</p>
          <div className="mt-2 flex gap-2">
            <Button variant="destructive" size="sm" className="h-7 flex-1" onClick={() => onDelete(workflow.id)}>
              Delete
            </Button>
            <Button variant="outline" size="sm" className="h-7 flex-1" onClick={() => setIsConfirming(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <p className="mt-4 text-xs text-muted-foreground">
          {workflow.nodeCount} step{workflow.nodeCount === 1 ? "" : "s"}
        </p>
      )}
    </div>
  );
});
