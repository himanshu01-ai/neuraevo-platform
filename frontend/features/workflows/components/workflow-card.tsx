"use client";

import { memo, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Archive,
  ArchiveRestore,
  Copy,
  Ellipsis,
  Pencil,
  Send,
  Settings,
  Trash2,
  Undo2,
  Workflow as WorkflowIcon,
} from "lucide-react";
import type { WorkflowSummary } from "@/services/workflows";
import { Button } from "@/components/ui/button";
import { DropdownMenu, type DropdownItem } from "@/components/ui/dropdown-menu";
import { StatusBadge } from "@/components/ui/status-badge";

export interface WorkflowCardProps {
  workflow: WorkflowSummary;
  onDuplicate: (workflow: WorkflowSummary) => void;
  onPublish: (workflow: WorkflowSummary) => void;
  onUnpublish: (workflow: WorkflowSummary) => void;
  onArchive: (workflow: WorkflowSummary) => void;
  onRestore: (workflow: WorkflowSummary) => void;
  onDelete: (workflow: WorkflowSummary) => void;
  /** Refuses the delete confirm while another action is already in flight. */
  isBusy?: boolean;
}

/**
 * One workflow in the list: what it is, where it is in its lifecycle, and how to
 * act on it.
 *
 * The action menu is lifecycle-aware — publish or unpublish, archive or restore,
 * never both — because only one of each pair is ever a legal backend move. An
 * archived workflow offers restore and hides editing, so a retired workflow is
 * viewable but not quietly editable.
 *
 * Delete asks first, inline. Removing someone's work on a single click of a menu
 * item is not a thing to do, and the confirmation lives here so the list doesn't
 * have to track which card is asking.
 */
export const WorkflowCard = memo(function WorkflowCard({
  workflow,
  onDuplicate,
  onPublish,
  onUnpublish,
  onArchive,
  onRestore,
  onDelete,
  isBusy = false,
}: WorkflowCardProps) {
  const [isConfirming, setIsConfirming] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);

  const isArchived = workflow.lifecycle === "ARCHIVED";
  const isPublished = workflow.lifecycle === "PUBLISHED";

  // Choosing Delete closes the menu, which leaves focus nowhere. Move it to the
  // confirmation — on Cancel, the safe half, so a stray Enter dismisses.
  useEffect(() => {
    if (isConfirming) cancelRef.current?.focus();
  }, [isConfirming]);

  // Built in lifecycle order so the menu reads predictably. Editing and the
  // publish/unpublish toggle drop out when archived — those moves are illegal
  // until it's restored.
  const items: DropdownItem[] = [];
  if (!isArchived) {
    items.push({
      key: "edit",
      label: "Open in builder",
      icon: Pencil,
      href: `/workspace/workflows/${workflow.id}/builder`,
    });
    items.push({
      key: "settings",
      label: "Settings",
      icon: Settings,
      href: `/workspace/workflows/${workflow.id}/settings`,
    });
    items.push(
      isPublished
        ? { key: "unpublish", label: "Move to draft", icon: Undo2, onSelect: () => onUnpublish(workflow) }
        : { key: "publish", label: "Publish", icon: Send, onSelect: () => onPublish(workflow) }
    );
  }
  items.push({ key: "duplicate", label: "Duplicate", icon: Copy, onSelect: () => onDuplicate(workflow) });
  items.push(
    isArchived
      ? { key: "restore", label: "Restore", icon: ArchiveRestore, onSelect: () => onRestore(workflow) }
      : { key: "archive", label: "Archive", icon: Archive, onSelect: () => onArchive(workflow) }
  );
  items.push({
    key: "delete",
    label: "Delete",
    icon: Trash2,
    destructive: true,
    onSelect: () => setIsConfirming(true),
  });

  return (
    <div className="flex flex-col rounded-lg border bg-card p-5 shadow-sm transition-all hover:border-primary/30 hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <span className="inline-flex size-9 items-center justify-center rounded-md bg-primary/10 text-primary">
          <WorkflowIcon className="size-5" aria-hidden="true" />
        </span>
        <div className="flex items-center gap-1.5">
          <StatusBadge kind="workflow-lifecycle" status={workflow.lifecycle} />
          <DropdownMenu
            menuLabel={`Actions for ${workflow.name}`}
            align="end"
            items={items}
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
          <p className="text-xs text-destructive">Delete “{workflow.name}”? This can&apos;t be undone.</p>
          <div className="mt-2 flex gap-2">
            <Button
              variant="destructive"
              size="sm"
              className="h-7 flex-1"
              disabled={isBusy}
              onClick={() => {
                setIsConfirming(false);
                onDelete(workflow);
              }}
            >
              Delete
            </Button>
            <Button
              ref={cancelRef}
              variant="outline"
              size="sm"
              className="h-7 flex-1"
              onClick={() => setIsConfirming(false)}
            >
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
