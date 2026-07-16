import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Workflows" };

const WorkflowList = dynamic(() => import("@/features/workflows").then((m) => m.WorkflowList), {
  loading: () => (
    <WorkspaceContent>
      <LoadingState rows={6} />
    </WorkspaceContent>
  ),
});

export default function WorkflowsPage() {
  return <WorkflowList />;
}
