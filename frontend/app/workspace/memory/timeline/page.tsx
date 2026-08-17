import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { Brain } from "lucide-react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Panel } from "@/features/workspace/panels/panel";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Memory timeline" };

const MemoryTimeline = dynamic(() => import("@/features/memory").then((m) => m.MemoryTimeline), {
  loading: () => <LoadingState rows={6} />,
});

export default function MemoryTimelinePage() {
  return (
    <WorkspaceContent>
      <WorkspaceHeader
        title="Timeline"
        description="Everything that's happened to your knowledge, newest first."
        actions={
          <Button variant="outline" href="/workspace/memory">
            <Brain className="size-4" aria-hidden="true" />
            Browse knowledge
          </Button>
        }
      />
      <div className="mt-6 max-w-3xl">
        <Panel title="History">
          <MemoryTimeline memoryId={null} showMemory />
        </Panel>
      </div>
    </WorkspaceContent>
  );
}
