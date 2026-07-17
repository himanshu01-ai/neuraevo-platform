import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { Brain } from "lucide-react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Knowledge graph" };

// The canvas is the heaviest thing in this feature; it loads on demand.
const KnowledgeGraphScreen = dynamic(
  () => import("@/features/memory").then((m) => m.KnowledgeGraphScreen),
  { loading: () => <LoadingState rows={6} /> }
);

export default function KnowledgeGraphPage() {
  return (
    <WorkspaceContent>
      <WorkspaceHeader
        title="Knowledge graph"
        description="How the knowledge connects to your employees, workflows and tasks."
        actions={
          <Button variant="outline" href="/workspace/memory">
            <Brain className="size-4" aria-hidden="true" />
            Browse knowledge
          </Button>
        }
      />
      <div className="mt-6">
        <KnowledgeGraphScreen />
      </div>
    </WorkspaceContent>
  );
}
