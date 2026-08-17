import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Memory" };

const MemoryDetails = dynamic(() => import("@/features/memory").then((m) => m.MemoryDetails), {
  loading: () => (
    <WorkspaceContent>
      <LoadingState rows={6} />
    </WorkspaceContent>
  ),
});

export default async function MemoryDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <MemoryDetails id={id} />;
}
