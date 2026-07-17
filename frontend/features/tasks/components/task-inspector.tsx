"use client";

import { motion } from "framer-motion";
import { MousePointerSquareDashed } from "lucide-react";
import { dependenciesOf, dependentsOf, nodeById, type TaskDetail } from "@/services/tasks";
import { NODE_LABEL, NODE_TONE } from "@/types/domain";
import { useExecutionStore } from "@/store/tasks";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { TONE_DOT, TONE_VARIANT } from "@/components/ui/status-badge";
import { ExecutionMonitor } from "../monitoring/execution-monitor";
import { EXECUTION_NODE_META } from "../models/execution-nodes";
import { cn } from "@/lib/utils";

export interface TaskInspectorProps {
  task: TaskDetail;
}

/**
 * The right-hand column: the run as a whole, or the node you clicked.
 *
 * With nothing selected it monitors the run; select a node and it becomes that
 * node's record. The two are one panel rather than two because they answer the
 * same question at different depths, and a screen that shows both at once makes
 * you work out which one you're reading.
 *
 * The connections list is what makes the graph keyboard-usable: the SVG edges
 * are decorative, so this states in words — and in focusable buttons — what each
 * node runs after and what waits on it.
 */
export function TaskInspector({ task }: TaskInspectorProps) {
  const selectedNodeId = useExecutionStore((s) => s.selectedNodeId);
  const selectNode = useExecutionStore((s) => s.selectNode);
  const node = nodeById(task.graph, selectedNodeId);

  if (!node) {
    return (
      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Execution</h3>
          <p className="text-xs text-muted-foreground">Select a node to inspect it.</p>
        </div>
        {task.graph.nodes.length === 0 ? (
          <EmptyState
            compact
            icon={MousePointerSquareDashed}
            title="Nothing running"
            description="This task has no run to inspect yet."
          />
        ) : (
          <ExecutionMonitor monitor={task.monitor} graph={task.graph} />
        )}
      </div>
    );
  }

  const meta = EXECUTION_NODE_META[node.kind];
  const Icon = meta.icon;
  const tone = NODE_TONE[node.status];
  const runsAfter = dependenciesOf(task.graph, node.id);
  const waiting = dependentsOf(task.graph, node.id);

  const connectionList = (ids: string[], emptyLabel: string) =>
    ids.length === 0 ? (
      <p className="mt-1.5 text-sm text-muted-foreground">{emptyLabel}</p>
    ) : (
      <ul className="mt-1.5 space-y-1">
        {ids.map((id) => {
          const other = nodeById(task.graph, id);
          if (!other) return null;
          return (
            <li key={id}>
              <button
                type="button"
                onClick={() => selectNode(id)}
                className="w-full truncate rounded-sm px-2 py-1 text-left text-sm text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {other.name}
              </button>
            </li>
          );
        })}
      </ul>
    );

  return (
    <motion.div
      key={node.id}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-4"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
            <Icon className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-foreground">{node.name}</h3>
            <p className="truncate text-xs text-muted-foreground">{meta.label}</p>
          </div>
        </div>
        <Badge variant={TONE_VARIANT[tone]} className="shrink-0">
          <span aria-hidden="true" className={cn("size-1.5 shrink-0 rounded-full", TONE_DOT[tone])} />
          {NODE_LABEL[node.status]}
        </Badge>
      </div>

      <p className="text-sm leading-relaxed text-muted-foreground">{node.detail}</p>

      <div className="border-t pt-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Runs after</h4>
        {connectionList(runsAfter, "Nothing — this is where the run starts.")}
      </div>

      <div className="border-t pt-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Waiting on this</h4>
        {connectionList(waiting, "Nothing — this is where the run ends.")}
      </div>

      <div className="border-t pt-3">
        <button
          type="button"
          onClick={() => selectNode(null)}
          className="rounded-sm text-xs font-medium text-primary transition-colors hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Back to the run
        </button>
      </div>
    </motion.div>
  );
}
