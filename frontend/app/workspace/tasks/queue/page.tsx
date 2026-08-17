import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { ListChecks } from "lucide-react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Queue" };

// The queue is a side trip from the board, so it loads on demand.
const QueueManager = dynamic(() => import("@/features/tasks").then((m) => m.QueueManager), {
  loading: () => <LoadingState rows={4} />,
});

export default function TaskQueuePage() {
  return (
    <WorkspaceContent>
      <WorkspaceHeader
        title="Queue"
        description="What's waiting, in the order the platform will run it."
        actions={
          <Button variant="outline" href="/workspace/tasks">
            <ListChecks className="size-4" aria-hidden="true" />
            All tasks
          </Button>
        }
      />
      <div className="mt-6 max-w-3xl">
        <QueueManager />
      </div>
    </WorkspaceContent>
  );
}
