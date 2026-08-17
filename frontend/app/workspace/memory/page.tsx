import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Memory" };

const KnowledgeBrowser = dynamic(() => import("@/features/memory").then((m) => m.KnowledgeBrowser), {
  loading: () => (
    <WorkspaceContent>
      <LoadingState rows={6} />
    </WorkspaceContent>
  ),
});

export default function MemoryPage() {
  return <KnowledgeBrowser />;
}
