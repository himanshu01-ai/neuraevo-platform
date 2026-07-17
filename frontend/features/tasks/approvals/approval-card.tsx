"use client";

import { memo, useId, useState } from "react";
import Link from "next/link";
import { Check, X } from "lucide-react";
import type { Approval } from "@/services/tasks";
import { APPROVAL_LABEL, APPROVAL_TONE } from "@/types/domain";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { TONE_DOT, TONE_VARIANT } from "@/components/ui/status-badge";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export interface ApprovalCardProps {
  approval: Approval;
  onDecide: (approvalId: string, status: "APPROVED" | "REJECTED", comment: string) => void;
  isPending?: boolean;
  /** Shows which task this belongs to — for the inbox, where they're mixed. */
  showTask?: boolean;
}

/**
 * One decision waiting on a person: what's being asked, who asked, who's on the
 * hook, and the two ways out.
 *
 * A decided approval keeps its comment and loses its buttons — the record of why
 * is the point, and re-deciding isn't offered because the adapter refuses it.
 *
 * Rejecting asks for a comment first. Approving doesn't: saying yes to what's
 * already described in front of you needs no justification, but telling someone
 * their work was turned down without a word is how you make a person guess.
 */
export const ApprovalCard = memo(function ApprovalCard({
  approval,
  onDecide,
  isPending = false,
  showTask = false,
}: ApprovalCardProps) {
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const commentId = useId();

  const isDecided = approval.status !== "PENDING";
  const tone = APPROVAL_TONE[approval.status];

  const handleReject = () => {
    if (!comment.trim()) {
      setError("Say why, so the work can be fixed rather than guessed at.");
      return;
    }
    onDecide(approval.id, "REJECTED", comment);
  };

  return (
    <div className="flex flex-col rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          {showTask ? (
            <p className="truncate text-xs text-muted-foreground">
              <Link
                href={`/workspace/tasks/${approval.taskId}`}
                className="rounded-sm transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {approval.taskName}
              </Link>
            </p>
          ) : null}
          <h4 className="mt-0.5 truncate text-sm font-semibold text-foreground">{approval.title}</h4>
        </div>
        <Badge variant={TONE_VARIANT[tone]} className="shrink-0">
          <span aria-hidden="true" className={cn("size-1.5 shrink-0 rounded-full", TONE_DOT[tone])} />
          {APPROVAL_LABEL[approval.status]}
        </Badge>
      </div>

      <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">{approval.description}</p>

      <dl className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs">
        <div className="flex items-center gap-1.5">
          <dt className="text-muted-foreground">Requested by</dt>
          <dd className="flex items-center gap-1.5 font-medium text-foreground">
            <Avatar name={approval.requestedBy} className="size-4 text-[0.5rem]" />
            {approval.requestedBy}
          </dd>
        </div>
        <div className="flex items-center gap-1.5">
          <dt className="text-muted-foreground">Reviewer</dt>
          <dd className="font-medium text-foreground">{approval.assignedReviewer}</dd>
        </div>
      </dl>

      {isDecided ? (
        approval.comment ? (
          <blockquote className="mt-3 border-l-2 border-border pl-3 text-sm text-muted-foreground">
            <span className="sr-only">Reviewer comment: </span>
            {approval.comment}
          </blockquote>
        ) : (
          <p className="mt-3 text-xs text-muted-foreground">Decided without a comment.</p>
        )
      ) : (
        <div className="mt-3 space-y-2 border-t pt-3">
          <Label htmlFor={commentId} className="text-xs">
            Comment
          </Label>
          <Textarea
            id={commentId}
            rows={2}
            value={comment}
            onChange={(event) => {
              setComment(event.target.value);
              setError(null);
            }}
            placeholder="Optional when approving; required when rejecting."
            aria-invalid={Boolean(error)}
            aria-describedby={error ? `${commentId}-err` : undefined}
            className="text-xs"
          />
          {error ? (
            <p id={`${commentId}-err`} role="alert" className="text-xs font-medium text-destructive">
              {error}
            </p>
          ) : null}

          <div className="flex gap-2">
            <Button
              size="sm"
              className="flex-1"
              disabled={isPending}
              onClick={() => onDecide(approval.id, "APPROVED", comment)}
            >
              <Check className="size-4" aria-hidden="true" />
              Approve
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 text-destructive hover:bg-destructive/10"
              disabled={isPending}
              onClick={handleReject}
            >
              <X className="size-4" aria-hidden="true" />
              Reject
            </Button>
          </div>
        </div>
      )}
    </div>
  );
});
