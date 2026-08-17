import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Tasks" };

const TaskDirectory = dynamic(() => import("@/features/tasks").then((m) => m.TaskDirectory), {
  loading: () => (
    <WorkspaceContent>
      <LoadingState rows={6} />
    </WorkspaceContent>
  ),
});

export default function TasksPage() {
  return <TaskDirectory />;
}
