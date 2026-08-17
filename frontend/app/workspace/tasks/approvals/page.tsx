import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { ListChecks } from "lucide-react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Task approvals" };

// The inbox is a side trip from the board, so it loads on demand.
const TaskApprovalsInbox = dynamic(() => import("@/features/tasks").then((m) => m.TaskApprovalsInbox), {
  loading: () => <LoadingState rows={4} />,
});

export default function TaskApprovalsPage() {
  return (
    <WorkspaceContent>
      <WorkspaceHeader
        title="Approvals"
        description="Decisions your AI employees are waiting on."
        actions={
          <Button variant="outline" href="/workspace/tasks">
            <ListChecks className="size-4" aria-hidden="true" />
            All tasks
          </Button>
        }
      />
      <div className="mt-6">
        <TaskApprovalsInbox />
      </div>
    </WorkspaceContent>
  );
}
