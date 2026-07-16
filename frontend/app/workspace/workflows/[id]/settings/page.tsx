import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Workflow settings" };

const WorkflowSettingsScreen = dynamic(
  () => import("@/features/workflows").then((m) => m.WorkflowSettingsScreen),
  {
    loading: () => (
      <WorkspaceContent>
        <LoadingState rows={5} />
      </WorkspaceContent>
    ),
  }
);

export default async function WorkflowSettingsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <WorkflowSettingsScreen id={id} />;
}
