import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Memory dashboard" };

const MemoryDashboard = dynamic(() => import("@/features/memory").then((m) => m.MemoryDashboard), {
  loading: () => (
    <WorkspaceContent>
      <LoadingState rows={6} />
    </WorkspaceContent>
  ),
});

export default function MemoryDashboardPage() {
  return <MemoryDashboard />;
}
