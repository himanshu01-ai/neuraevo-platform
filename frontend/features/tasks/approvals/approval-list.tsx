"use client";

import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { useAllApprovals, useDecideApproval, useTaskApprovals } from "../hooks/use-tasks";
import { ApprovalCard } from "./approval-card";
import { cn } from "@/lib/utils";

export interface ApprovalListProps {
  /** `null` for the reviewer's inbox — every approval across every task. */
  taskId: string | null;
  className?: string;
}

/**
 * Approvals waiting on a person: one task's, or the whole inbox.
 *
 * Both use the same card and the same mutation, so a decision made in the dock
 * and one made in the inbox are the same operation — and Sprint 17.8 wires one
 * endpoint, not two.
 */
export function ApprovalList({ taskId, className }: ApprovalListProps) {
  const scoped = useTaskApprovals(taskId);
  const inbox = useAllApprovals();
  const decide = useDecideApproval();
  const [error, setError] = useState<string | null>(null);

  // One of the two is always disabled by its `enabled` flag, so only the one
  // this list is scoped to ever fetches.
  const query = taskId === null ? inbox : scoped;

  if (query.isPending) return <LoadingState rows={3} className={className} />;

  if (query.isError) {
    return (
      <ErrorState
        compact
        title="Couldn't load approvals"
        description="What's waiting on you couldn't be loaded."
        onRetry={() => void query.refetch()}
        className={className}
      />
    );
  }

  const approvals = query.data ?? [];

  if (approvals.length === 0) {
    return (
      <EmptyState
        compact
        icon={ShieldCheck}
        title="Nothing waiting on you"
        description={
          taskId === null
            ? "When an employee needs a sign-off, it'll show up here."
            : "This task hasn't asked for a decision."
        }
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      {error ? <Alert variant="error">{error}</Alert> : null}

      <div className="grid gap-3 lg:grid-cols-2">
        {approvals.map((approval) => (
          <ApprovalCard
            key={approval.id}
            approval={approval}
            showTask={taskId === null}
            isPending={decide.isPending}
            onDecide={(approvalId, status, comment) => {
              setError(null);
              decide.mutate(
                { approvalId, status, comment },
                { onError: () => setError("That decision couldn't be recorded. Try again in a moment.") }
              );
            }}
          />
        ))}
      </div>
    </div>
  );
}
