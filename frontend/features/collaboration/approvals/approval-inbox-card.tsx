"use client";

import { memo, useState } from "react";
import { ShieldCheck } from "lucide-react";
import type { CollaborationApproval } from "@/services/collaboration";
import { PRIORITY_LABEL, PRIORITY_TONE } from "@/types/domain";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { StatusBadge, TONE_VARIANT } from "@/components/ui/status-badge";
import { Textarea } from "@/components/ui/textarea";
import { formatDateTime } from "@/utils/format";
import { EntityReferenceCard } from "../references/entity-reference-card";
import { cn } from "@/lib/utils";

export interface ApprovalInboxCardProps {
  approval: CollaborationApproval;
  onDecide: (id: string, status: "APPROVED" | "REJECTED", comment: string) => void;
  isDeciding?: boolean;
  className?: string;
}

/**
 * One approval in the inbox: what's asked, who asked, its priority, and the
 * record it concerns. Pending shows the decision controls and a comment field;
 * a decided card shows the outcome and the note. Status resolves through
 * `StatusBadge`'s approval vocabulary — the same one the task inbox uses.
 *
 * Memoized like every other card rendered in a list, so typing a comment in one
 * card doesn't repaint the rest of the inbox.
 */
export const ApprovalInboxCard = memo(function ApprovalInboxCard({
  approval,
  onDecide,
  isDeciding = false,
  className,
}: ApprovalInboxCardProps) {
  const [comment, setComment] = useState("");
  const pending = approval.status === "PENDING";

  return (
    <section
      aria-label={`Approval: ${approval.title}`}
      className={cn("rounded-lg border bg-card p-4 shadow-sm", pending && "border-warning/40", className)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-warning/10 text-warning">
            <ShieldCheck className="size-4" aria-hidden="true" />
          </span>
          <h3 className="truncate text-sm font-semibold text-foreground">{approval.title}</h3>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <Badge variant={TONE_VARIANT[PRIORITY_TONE[approval.priority]]}>{PRIORITY_LABEL[approval.priority]}</Badge>
          <StatusBadge kind="approval" status={approval.status} />
        </div>
      </div>

      <p className="mt-2 text-sm text-muted-foreground">{approval.description}</p>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <Avatar name={approval.requestedBy.name} className="size-5 text-[0.625rem]" />
          {approval.requestedBy.name}
        </span>
        <span aria-hidden="true">·</span>
        <time dateTime={approval.createdAt}>{formatDateTime(approval.createdAt)}</time>
      </div>

      {approval.entity ? <EntityReferenceCard entity={approval.entity} className="mt-3" /> : null}

      {pending ? (
        <div className="mt-3 space-y-2 border-t pt-3">
          <label htmlFor={`approval-comment-${approval.id}`} className="text-xs font-medium text-muted-foreground">
            Comment (optional)
          </label>
          <Textarea
            id={`approval-comment-${approval.id}`}
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Why you decided this way…"
            disabled={isDeciding}
          />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => onDecide(approval.id, "APPROVED", comment)} disabled={isDeciding}>
              Approve
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="text-destructive hover:text-destructive"
              onClick={() => onDecide(approval.id, "REJECTED", comment)}
              disabled={isDeciding}
            >
              Reject
            </Button>
          </div>
        </div>
      ) : approval.comment ? (
        <p className="mt-3 border-t pt-3 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Reviewer note: </span>
          {approval.comment}
        </p>
      ) : null}
    </section>
  );
});
