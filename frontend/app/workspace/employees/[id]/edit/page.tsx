import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Edit employee" };

const ExistingEmployeeBuilder = dynamic(
  () => import("@/features/employees").then((m) => m.ExistingEmployeeBuilder),
  {
    loading: () => (
      <WorkspaceContent>
        <LoadingState rows={6} />
      </WorkspaceContent>
    ),
  }
);

export default async function EditEmployeePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ExistingEmployeeBuilder id={id} />;
}
