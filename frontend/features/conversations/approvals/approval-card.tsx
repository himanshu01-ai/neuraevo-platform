"use client";

import { useState } from "react";
import type { ApprovalPayload } from "@/services/conversations";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { Textarea } from "@/components/ui/textarea";
import { MESSAGE_KIND_META } from "../models/message-kinds";
import { cn } from "@/lib/utils";

export interface ApprovalCardProps {
  approval: ApprovalPayload;
  /** Called with the decision and the reviewer's note. UI only — nothing runs. */
  onDecide: (status: "APPROVED" | "REJECTED", comment: string) => void;
  isDeciding?: boolean;
  className?: string;
}

/**
 * An in-thread approval request. Pending shows the decision controls and a
 * comment field; a decided card shows the outcome and the note that came with
 * it. The status resolves through `StatusBadge`'s approval vocabulary, the
 * same one the task inbox uses.
 */
export function ApprovalCard({ approval, onDecide, isDeciding = false, className }: ApprovalCardProps) {
  const [comment, setComment] = useState("");
  const Icon = MESSAGE_KIND_META.approval_request.icon;
  const pending = approval.status === "PENDING";

  return (
    <section
      aria-label={`Approval request: ${approval.title}`}
      className={cn("rounded-lg border bg-card p-4 shadow-sm", pending && "border-warning/40", className)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-warning/10 text-warning">
            <Icon className="size-4" aria-hidden="true" />
          </span>
          <h4 className="truncate text-sm font-semibold text-foreground">{approval.title}</h4>
        </div>
        <StatusBadge kind="approval" status={approval.status} className="shrink-0" />
      </div>

      <p className="mt-2 text-sm text-muted-foreground">{approval.description}</p>

      {pending ? (
        <div className="mt-3 space-y-2 border-t pt-3">
          <label htmlFor={`comment_${approval.approvalId}`} className="text-xs font-medium text-muted-foreground">
            Comment (optional)
          </label>
          <Textarea
            id={`comment_${approval.approvalId}`}
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Why you decided this way…"
            disabled={isDeciding}
          />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => onDecide("APPROVED", comment)} disabled={isDeciding}>
              Approve
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="text-destructive hover:text-destructive"
              onClick={() => onDecide("REJECTED", comment)}
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
}
