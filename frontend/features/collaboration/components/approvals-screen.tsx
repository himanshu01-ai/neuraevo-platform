"use client";

import { useCallback, useMemo, useState } from "react";
import { ShieldCheck } from "lucide-react";
import type { ApprovalStatus } from "@/types/domain";
import { APPROVAL_LABEL, APPROVAL_STATUS } from "@/types/domain";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Select } from "@/components/ui/select";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { Reveal } from "@/components/motion/reveal";
import { useApprovals, useDecideApproval } from "../hooks/use-collaboration";
import { ApprovalInboxCard } from "../approvals/approval-inbox-card";
import { CollaborationHeader } from "./collaboration-header";
import { FeedLoading } from "./collaboration-loading";

/**
 * The Approvals inbox: every sign-off the workspace is waiting on, filterable
 * by status. Deciding is UI only — the card flips to the outcome and records
 * the reviewer's note; nothing runs. Pending lead the list so the actionable
 * ones are first.
 */
export function ApprovalsScreen() {
  const approvals = useApprovals();
  const decide = useDecideApproval();
  const [status, setStatus] = useState<ApprovalStatus | "ALL">("ALL");
  const [notice, setNotice] = useState<{ tone: "info" | "error"; message: string } | null>(null);

  const rows = useMemo(() => {
    const all = approvals.data ?? [];
    const filtered = status === "ALL" ? all : all.filter((a) => a.status === status);
    // Pending first, then by recency (the adapter already sorts by recency).
    return [...filtered].sort((a, b) => Number(b.status === "PENDING") - Number(a.status === "PENDING"));
  }, [approvals.data, status]);

  const handleDecide = useCallback(
    (id: string, decision: "APPROVED" | "REJECTED", comment: string) => {
      setNotice(null);
      decide.mutate(
        { approvalId: id, status: decision, comment },
        {
          onSuccess: (approval) =>
            setNotice({ tone: "info", message: `${approval.title} — ${APPROVAL_LABEL[approval.status].toLowerCase()}.` }),
          onError: (error) =>
            setNotice({ tone: "error", message: error instanceof Error ? error.message : "That couldn't be recorded." }),
        }
      );
    },
    [decide]
  );

  const pendingCount = (approvals.data ?? []).filter((a) => a.status === "PENDING").length;

  return (
    <WorkspaceContent>
      <Reveal>
        <CollaborationHeader
          title="Approvals"
          description={
            pendingCount > 0
              ? `${pendingCount} ${pendingCount === 1 ? "approval is" : "approvals are"} waiting on you.`
              : "Sign-offs your AI employees have requested."
          }
          actions={
            <div>
              <label className="sr-only" htmlFor="approval-status">
                Filter by status
              </label>
              <Select
                id="approval-status"
                value={status}
                onChange={(e) => setStatus(e.target.value as ApprovalStatus | "ALL")}
                className="h-9 w-40"
              >
                <option value="ALL">All statuses</option>
                {APPROVAL_STATUS.map((value) => (
                  <option key={value} value={value}>
                    {APPROVAL_LABEL[value]}
                  </option>
                ))}
              </Select>
            </div>
          }
        />
      </Reveal>

      {notice ? (
        <Alert variant={notice.tone === "error" ? "error" : "info"} className="mt-4">
          {notice.message}
        </Alert>
      ) : null}

      <div className="mt-4 max-w-3xl">
        {approvals.isError ? (
          <ErrorState
            title="Couldn't load approvals"
            description="Your approvals couldn't be loaded. Try again in a moment."
            onRetry={() => void approvals.refetch()}
          />
        ) : approvals.isPending ? (
          <FeedLoading rows={3} />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={ShieldCheck}
            title={status === "ALL" ? "No approvals" : "None match"}
            description={
              status === "ALL"
                ? "When an AI employee needs a sign-off, it'll appear here."
                : "No approvals in that status. Try another filter."
            }
          />
        ) : (
          <ul className="flex flex-col gap-3" aria-label="Approvals">
            {rows.map((approval) => (
              <li key={approval.id}>
                <ApprovalInboxCard approval={approval} onDecide={handleDecide} isDeciding={decide.isPending} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </WorkspaceContent>
  );
}
