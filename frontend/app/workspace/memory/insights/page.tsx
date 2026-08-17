import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { Brain } from "lucide-react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Memory insights" };

const InsightsPanel = dynamic(() => import("@/features/memory").then((m) => m.InsightsPanel), {
  loading: () => <LoadingState rows={6} />,
});

export default function MemoryInsightsPage() {
  return (
    <WorkspaceContent>
      <WorkspaceHeader
        title="Insights"
        description="What the knowledge looks like as a whole — counts, not conclusions."
        actions={
          <Button variant="outline" href="/workspace/memory">
            <Brain className="size-4" aria-hidden="true" />
            Browse knowledge
          </Button>
        }
      />
      <div className="mt-6">
        <InsightsPanel />
      </div>
    </WorkspaceContent>
  );
}
