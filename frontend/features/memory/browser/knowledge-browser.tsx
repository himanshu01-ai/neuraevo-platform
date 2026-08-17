"use client";

import { useEffect } from "react";
import dynamic from "next/dynamic";
import { useMemoryStore } from "@/store/memory";
import { ErrorState } from "@/components/ui/error-state";
import { Reveal } from "@/components/motion/reveal";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import {
  useCollections,
  useKnowledgeGraph,
  useMemoryDetail,
  useMemoryList,
  useWorkspaceQuery,
} from "../hooks/use-memory";
import { MemoryToolbar } from "../components/memory-toolbar";
import {
  InspectorLoading,
  KnowledgeViewerLoading,
  MemoryCardGridLoading,
  MemoryEmptyState,
  MemoryListLoading,
} from "../components/memory-states";
import { MemoryList } from "./memory-list";
import { MemoryTree } from "./memory-tree";

/**
 * The memory workspace: the shelves on the left, what you're reading in the
 * middle, everything about it on the right, and its record below.
 *
 * The viewer, the inspector and the dock are the heavy half of this screen and
 * none is needed to render the tree, so all three load on demand — the shelves
 * paint first and the panels arrive with their own placeholders.
 *
 * Below `xl` the three columns stack in reading order (tree, viewer, inspector,
 * dock) rather than switching on a media query: a layout that only depends on
 * CSS can't disagree with the server about what to render on first paint.
 *
 * Nothing on this screen retrieves or ranks anything. It shows what is stored.
 */

const KnowledgeViewer = dynamic(() => import("../knowledge/knowledge-viewer").then((m) => m.KnowledgeViewer), {
  loading: () => <KnowledgeViewerLoading />,
});

const MemoryInspector = dynamic(
  () => import("../components/memory-inspector").then((m) => m.MemoryInspector),
  { loading: () => <InspectorLoading /> }
);

const MemoryDock = dynamic(() => import("../components/memory-dock").then((m) => m.MemoryDock), {
  loading: () => <div className="h-64 rounded-lg border bg-card shadow-sm" />,
});

export function KnowledgeBrowser() {
  const query = useWorkspaceQuery();
  const list = useMemoryList(query);
  const collections = useCollections();
  const graph = useKnowledgeGraph();

  const viewMode = useMemoryStore((s) => s.viewMode);
  const selectedMemoryId = useMemoryStore((s) => s.selectedMemoryId);
  const selectMemory = useMemoryStore((s) => s.selectMemory);

  const detail = useMemoryDetail(selectedMemoryId);

  // A selection outlives the list it came from: a memory filtered out of view
  // would otherwise leave the viewer showing something the tree doesn't offer.
  useEffect(() => {
    if (!list.data || selectedMemoryId === null) return;
    if (!list.data.some((memory) => memory.id === selectedMemoryId)) selectMemory(null);
  }, [list.data, selectedMemoryId, selectMemory]);

  const memories = () => {
    if (list.isError) {
      return (
        <ErrorState
          title="Couldn't load knowledge"
          description="What your employees know couldn't be loaded. Try again in a moment."
          onRetry={() => void list.refetch()}
        />
      );
    }

    if (list.isPending) {
      return viewMode === "grid" ? (
        <MemoryCardGridLoading count={2} className="sm:grid-cols-1 xl:grid-cols-1" />
      ) : (
        <MemoryListLoading />
      );
    }

    if (list.data.length === 0) {
      return (
        <MemoryEmptyState
          compact
          title="Nothing matches"
          description="Try a different word, or clear the filters."
          showActions={false}
        />
      );
    }

    return <MemoryList memories={list.data} viewMode={viewMode} />;
  };

  return (
    <WorkspaceContent>
      <Reveal>
        <WorkspaceHeader
          title="Memory"
          description="Everything your AI employees know, and where each piece of it came from."
        />
      </Reveal>

      <div className="mt-6">
        <MemoryToolbar />
      </div>

      <div className="mt-4 flex flex-col gap-4 xl:flex-row">
        <div className="min-w-0 xl:w-72 xl:shrink-0">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Memory tree
          </h2>

          {collections.isPending ? (
            <MemoryListLoading count={4} />
          ) : collections.isError ? (
            <ErrorState
              compact
              title="Couldn't load collections"
              onRetry={() => void collections.refetch()}
            />
          ) : (
            <MemoryTree collections={collections.data} memories={list.data ?? []} />
          )}

          <div className="mt-4 border-t pt-4">{memories()}</div>
        </div>

        <div className="min-w-0 flex-1">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Knowledge viewer
          </h2>
          <section
            aria-label="Knowledge viewer"
            className="rounded-lg border bg-card p-5 shadow-sm xl:max-h-[40rem] xl:overflow-y-auto"
          >
            <KnowledgeViewer memoryId={selectedMemoryId} />
          </section>
        </div>

        <div className="min-w-0 xl:w-80 xl:shrink-0">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Inspector
          </h2>
          <section
            aria-label="Memory inspector"
            className="rounded-lg border bg-card p-4 shadow-sm xl:max-h-[40rem] xl:overflow-y-auto"
          >
            {detail.isPending && selectedMemoryId ? (
              <InspectorLoading />
            ) : (
              <MemoryInspector memory={detail.data ?? null} graph={graph.data} />
            )}
          </section>
        </div>
      </div>

      <div className="mt-4">
        <MemoryDock memory={detail.data ?? null} graph={graph.data} />
      </div>
    </WorkspaceContent>
  );
}
