import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Employee" };

const EmployeeProfile = dynamic(() => import("@/features/employees").then((m) => m.EmployeeProfile), {
  loading: () => (
    <WorkspaceContent>
      <LoadingState rows={6} />
    </WorkspaceContent>
  ),
});

export default async function EmployeeProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <EmployeeProfile id={id} />;
}
