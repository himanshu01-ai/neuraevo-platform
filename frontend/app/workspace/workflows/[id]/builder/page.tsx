import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkflowLoadingState } from "@/features/workflows";

export const metadata: Metadata = { title: "Workflow builder" };

const ExistingWorkflowBuilder = dynamic(
  () => import("@/features/workflows").then((m) => m.ExistingWorkflowBuilder),
  { loading: () => <WorkflowLoadingState /> }
);

export default async function WorkflowBuilderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ExistingWorkflowBuilder id={id} />;
}
