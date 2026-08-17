"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { History } from "lucide-react";
import { nodeById, type ExecutionGraph } from "@/services/tasks";
import { useExecutionStore } from "@/store/tasks";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { TONE_DOT } from "@/components/ui/status-badge";
import { useTaskTimeline } from "../hooks/use-tasks";
import { TIMELINE_EVENT_META } from "../models/timeline-events";
import { cn } from "@/lib/utils";

export interface ExecutionTimelineProps {
  taskId: string;
  graph: ExecutionGraph;
  /** Caps the list where space is tight (the dock); omit to show everything. */
  limit?: number;
  className?: string;
}

/**
 * What a run has done, newest first.
 *
 * Events are ordered, not timed: the platform reports a sequence, so the
 * timeline shows order and refuses to invent clock times it doesn't have.
 *
 * On virtualizing: a run's timeline is bounded by its steps — the longest
 * fixture is ten events, and the dock caps at six. Virtualizing tens of rows
 * costs a scroll container, a measurement pass and a pile of absolute
 * positioning to save nothing, so this renders the list plainly. The `limit`
 * prop is the seam if a backend ever returns thousands.
 *
 * An event that came from a node selects that node — the timeline and the graph
 * are two views of one run, and clicking a milestone should show you where it
 * happened.
 */
export function ExecutionTimeline({ taskId, graph, limit, className }: ExecutionTimelineProps) {
  const query = useTaskTimeline(taskId);
  const selectNode = useExecutionStore((s) => s.selectNode);
  const selectedNodeId = useExecutionStore((s) => s.selectedNodeId);

  const events = useMemo(() => {
    const rows = query.data ?? [];
    return limit ? rows.slice(0, limit) : rows;
  }, [query.data, limit]);

  if (query.isPending) return <LoadingState rows={4} className={className} />;

  if (query.isError) {
    return (
      <ErrorState
        compact
        title="Couldn't load the timeline"
        description="This task's history couldn't be loaded."
        onRetry={() => void query.refetch()}
        className={className}
      />
    );
  }

  if (events.length === 0) {
    return (
      <EmptyState
        compact
        icon={History}
        title="Nothing yet"
        description="This task hasn't done anything worth recording."
        className={className}
      />
    );
  }

  return (
    <ol className={cn("relative space-y-3", className)}>
      {/* One continuous rule behind the markers; hidden from the reading order. */}
      <span aria-hidden="true" className="absolute bottom-4 left-[15px] top-4 w-px bg-border" />

      {events.map((event, index) => {
        const meta = TIMELINE_EVENT_META[event.kind];
        const Icon = meta.icon;
        const node = nodeById(graph, event.nodeId);
        const isSelected = node !== null && node.id === selectedNodeId;

        return (
          <motion.li
            key={event.id}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2, delay: Math.min(index * 0.03, 0.24), ease: [0.16, 1, 0.3, 1] }}
            className="relative flex items-start gap-3"
          >
            <span className="relative z-10 inline-flex size-8 shrink-0 items-center justify-center rounded-full border bg-card text-muted-foreground">
              <Icon className="size-4" aria-hidden="true" />
              <span
                aria-hidden="true"
                className={cn(
                  "absolute -bottom-0.5 -right-0.5 size-2 rounded-full ring-2 ring-card",
                  TONE_DOT[meta.tone]
                )}
              />
            </span>

            <span className="min-w-0 flex-1 pt-1">
              {node ? (
                <button
                  type="button"
                  onClick={() => selectNode(node.id)}
                  className={cn(
                    "block w-full rounded-sm text-left text-sm transition-colors hover:text-primary",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    isSelected ? "font-medium text-primary" : "text-foreground"
                  )}
                >
                  {event.summary}
                </button>
              ) : (
                <span className="block text-sm text-foreground">{event.summary}</span>
              )}
              <span className="block text-xs text-muted-foreground">{meta.label}</span>
            </span>
          </motion.li>
        );
      })}
    </ol>
  );
}
