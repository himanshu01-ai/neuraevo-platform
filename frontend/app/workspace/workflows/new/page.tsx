import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkflowLoadingState } from "@/features/workflows";

export const metadata: Metadata = { title: "New workflow" };

// The builder is the heaviest screen in the workspace; keep it out of the shell.
const NewWorkflowBuilder = dynamic(() => import("@/features/workflows").then((m) => m.NewWorkflowBuilder), {
  loading: () => <WorkflowLoadingState />,
});

export default function NewWorkflowPage() {
  return <NewWorkflowBuilder />;
}
