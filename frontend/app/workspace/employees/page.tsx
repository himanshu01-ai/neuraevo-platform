import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "AI Employees" };

const EmployeeDirectory = dynamic(() => import("@/features/employees").then((m) => m.EmployeeDirectory), {
  loading: () => (
    <WorkspaceContent>
      <LoadingState rows={6} />
    </WorkspaceContent>
  ),
});

export default function EmployeesPage() {
  return <EmployeeDirectory />;
}
