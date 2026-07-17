import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { ListChecks } from "lucide-react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Task history" };

// History is a side trip from the board, so it loads on demand.
const TaskHistory = dynamic(() => import("@/features/tasks").then((m) => m.TaskHistory), {
  loading: () => <LoadingState rows={4} />,
});

export default function TaskHistoryPage() {
  return (
    <WorkspaceContent>
      <WorkspaceHeader
        title="History"
        description="Everything that's finished — completed, failed, or cancelled."
        actions={
          <Button variant="outline" href="/workspace/tasks">
            <ListChecks className="size-4" aria-hidden="true" />
            All tasks
          </Button>
        }
      />
      <div className="mt-6 max-w-4xl">
        <TaskHistory />
      </div>
    </WorkspaceContent>
  );
}
