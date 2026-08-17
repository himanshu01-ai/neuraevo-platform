import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

// Lazy-load the dashboard so the whole widget surface is code-split from the shell.
const DashboardHome = dynamic(() => import("@/features/dashboard").then((m) => m.DashboardHome), {
  loading: () => (
    <WorkspaceContent>
      <LoadingState rows={6} />
    </WorkspaceContent>
  ),
});

export default function WorkspacePage() {
  return <DashboardHome />;
}
