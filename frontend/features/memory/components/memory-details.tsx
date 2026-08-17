"use client";

import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Panel } from "@/features/workspace/panels/panel";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Reveal } from "@/components/motion/reveal";
import { useKnowledgeGraph, useMemoryDetail } from "../hooks/use-memory";
import { KnowledgeGraph } from "../graph/knowledge-graph";
import { KnowledgeViewer } from "../knowledge/knowledge-viewer";
import { MemoryTimeline } from "../timeline/memory-timeline";
import { GraphLoading, KnowledgeViewerLoading } from "./memory-states";
import { MemoryInspector } from "./memory-inspector";
import { RelationshipList } from "./relationship-list";

/**
 * One memory in full: what it says, what it touches, and everything known about
 * it — on a single page.
 *
 * The workspace splits these across three columns and a dock; here they're
 * together, because this page exists for the moment you want the whole picture
 * of one memory. The graph is narrowed to this memory's neighbourhood rather
 * than showing the whole map, since "what does *this* touch" is the question
 * being asked on a memory's own screen.
 *
 * Read-only. This sprint visualises memory; it doesn't edit it.
 */
export function MemoryDetails({ id }: { id: string }) {
  const query = useMemoryDetail(id);
  const graph = useKnowledgeGraph();

  if (query.isPending) {
    return (
      <WorkspaceContent>
        <KnowledgeViewerLoading />
      </WorkspaceContent>
    );
  }

  if (query.isError || !query.data) {
    return (
      <WorkspaceContent>
        <ErrorState
          title="Memory not found"
          description="This memory doesn't exist, or it was removed."
          action={
            <Button variant="outline" href="/workspace/memory">
              Back to memory
            </Button>
          }
        />
      </WorkspaceContent>
    );
  }

  const memory = query.data;

  return (
    <WorkspaceContent>
      <Reveal>
        <WorkspaceHeader
          title={memory.title}
          description={memory.summary}
          actions={
            <Button variant="ghost" size="icon" href="/workspace/memory" aria-label="Back to memory">
              <ArrowLeft className="size-4" aria-hidden="true" />
            </Button>
          }
        />
      </Reveal>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="min-w-0 space-y-6 lg:col-span-2">
          <Reveal>
            <Panel title="Content">
              <KnowledgeViewer memoryId={memory.id} />
            </Panel>
          </Reveal>

          <Reveal delay={0.05}>
            <Panel
              title="Relationships"
              description="What this memory is connected to."
              bodyClassName="p-0"
            >
              {graph.isPending ? (
                <GraphLoading className="h-[22rem] rounded-none border-0" />
              ) : graph.data ? (
                <KnowledgeGraph
                  graph={graph.data}
                  focusMemoryId={memory.id}
                  showLabels
                  className="h-[22rem] rounded-none border-0"
                />
              ) : null}

              {graph.data ? (
                <div className="border-t p-5">
                  <RelationshipList memory={memory} graph={graph.data} />
                </div>
              ) : null}
            </Panel>
          </Reveal>
        </div>

        <div className="min-w-0 space-y-6">
          <Reveal delay={0.05}>
            <Panel title="Details">
              <MemoryInspector memory={memory} graph={graph.data} />
            </Panel>
          </Reveal>

          <Reveal delay={0.1}>
            <Panel title="History" description="What's happened to this memory.">
              <MemoryTimeline memoryId={memory.id} />
            </Panel>
          </Reveal>
        </div>
      </div>
    </WorkspaceContent>
  );
}
