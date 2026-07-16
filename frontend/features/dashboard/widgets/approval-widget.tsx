"use client";

import { memo } from "react";
import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { PRIORITY_LABEL } from "@/types/domain";
import { WidgetShell } from "../components/widget-shell";
import { EntityList } from "../components/entity-list";
import { usePendingApprovals } from "../hooks/use-dashboard";

/**
 * Pending Approvals. Rows navigate to the approvals screen — approving is a
 * decision with real consequences and doesn't belong on a dashboard preview.
 */
export const ApprovalWidget = memo(function ApprovalWidget() {
  const query = usePendingApprovals();
  const approvals = query.data ?? [];

  return (
    <WidgetShell
      title="Pending approvals"
      description="Waiting on you."
      href="/workspace/approvals"
      isLoading={query.isPending}
      isError={query.isError}
      isEmpty={approvals.length === 0}
      isRefreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
      empty={
        <EmptyState
          compact
          icon={ShieldCheck}
          title="Nothing to approve"
          description="You're all caught up."
        />
      }
    >
      <EntityList
        label="Pending approvals"
        items={approvals.map((approval) => ({
          id: approval.id,
          title: approval.title,
          meta: `${approval.requestedBy} · ${PRIORITY_LABEL[approval.priority]} priority`,
          icon: ShieldCheck,
          href: "/workspace/approvals",
          isHighlighted: approval.status === "PENDING",
          trailing: <StatusBadge kind="approval" status={approval.status} />,
        }))}
      />
      <div className="mt-4 border-t pt-3">
        <Button variant="outline" size="sm" href="/workspace/approvals" className="w-full">
          Review approvals
        </Button>
      </div>
    </WidgetShell>
  );
});
