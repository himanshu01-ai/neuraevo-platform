import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { Brain } from "lucide-react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Collections" };

// A side trip from the browser, so it loads on demand.
const CollectionGrid = dynamic(() => import("@/features/memory").then((m) => m.CollectionGrid), {
  loading: () => <LoadingState rows={6} />,
});

export default function CollectionsPage() {
  return (
    <WorkspaceContent>
      <WorkspaceHeader
        title="Collections"
        description="The shelves your knowledge is filed on."
        actions={
          <Button variant="outline" href="/workspace/memory">
            <Brain className="size-4" aria-hidden="true" />
            Browse knowledge
          </Button>
        }
      />
      <div className="mt-6">
        <CollectionGrid />
      </div>
    </WorkspaceContent>
  );
}
