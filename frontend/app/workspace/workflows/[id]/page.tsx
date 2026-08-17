import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Workflow" };

const WorkflowDetails = dynamic(() => import("@/features/workflows").then((m) => m.WorkflowDetails), {
  loading: () => (
    <WorkspaceContent>
      <LoadingState rows={6} />
    </WorkspaceContent>
  ),
});

export default async function WorkflowDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <WorkflowDetails id={id} />;
}
