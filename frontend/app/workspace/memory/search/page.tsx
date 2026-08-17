import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { Brain } from "lucide-react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Panel } from "@/features/workspace/panels/panel";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Search knowledge" };

const SearchPanel = dynamic(() => import("@/features/memory").then((m) => m.SearchPanel), {
  loading: () => <LoadingState rows={4} />,
});

const SearchResults = dynamic(() => import("@/features/memory").then((m) => m.SearchResults), {
  loading: () => <LoadingState rows={4} />,
});

export default function MemorySearchPage() {
  return (
    <WorkspaceContent>
      <WorkspaceHeader
        title="Search"
        description="Narrow the knowledge down to what you're after."
        actions={
          <Button variant="outline" href="/workspace/memory">
            <Brain className="size-4" aria-hidden="true" />
            Browse knowledge
          </Button>
        }
      />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <div className="min-w-0 lg:w-80 lg:shrink-0">
          <Panel title="Filters" description="Every facet is a filter — nothing is ranked.">
            <SearchPanel />
          </Panel>
        </div>

        <div className="min-w-0 flex-1">
          <SearchResults />
        </div>
      </div>
    </WorkspaceContent>
  );
}
