"use client";

import { useMemo, useState } from "react";
import { Copy, MousePointerSquareDashed, Trash2, X } from "lucide-react";
import {
  dependenciesOf,
  dependentsOf,
  edgeExists,
  wouldCycle,
  type WorkflowGraph,
  type WorkflowNode,
} from "@/services/workflows";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { useBuilderStore } from "@/store/workflow";
import { NODE_TYPES } from "../models/node-types";
import { useWorkflowValidation } from "../hooks/use-workflow-validation";
import { PropertiesPanel } from "./properties-panel";

/** Steps this one could be wired to without repeating an edge or closing a loop. */
function connectableTargets(graph: WorkflowGraph, sourceId: string): WorkflowNode[] {
  return graph.nodes.filter(
    (n) => n.id !== sourceId && !edgeExists(graph, sourceId, n.id) && !wouldCycle(graph, sourceId, n.id)
  );
}

function ConnectionRow({ node, edgeId, label }: { node: WorkflowNode; edgeId: string; label: string }) {
  const deleteEdge = useBuilderStore((s) => s.deleteEdge);
  const selectNode = useBuilderStore((s) => s.selectNode);

  return (
    <li className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => selectNode(node.id)}
        className="min-w-0 flex-1 truncate rounded-md px-2 py-1.5 text-left text-sm text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {node.name}
      </button>
      <Button
        variant="ghost"
        size="icon"
        className="size-7 shrink-0 text-muted-foreground hover:text-destructive"
        onClick={() => deleteEdge(edgeId)}
        aria-label={`${label} ${node.name}`}
      >
        <X className="size-3.5" aria-hidden="true" />
      </Button>
    </li>
  );
}

/**
 * Everything about the selected step: its properties, how it's wired, what
 * validation says about it, and the fields the platform owns.
 *
 * The Connections section is the keyboard route to wiring a workflow — the
 * canvas handle needs a pointer, this doesn't.
 */
export function InspectorPanel() {
  const graph = useBuilderStore((s) => s.graph);
  const selectedNodeId = useBuilderStore((s) => s.selectedNodeId);
  const connectNodes = useBuilderStore((s) => s.connectNodes);
  const deleteNode = useBuilderStore((s) => s.deleteNode);
  const duplicateNode = useBuilderStore((s) => s.duplicateNode);
  const report = useWorkflowValidation();
  const [pendingTarget, setPendingTarget] = useState("");

  const node = graph.nodes.find((n) => n.id === selectedNodeId) ?? null;

  const dependencies = useMemo(
    () => (node ? dependenciesOf(graph, node.id) : []),
    [graph, node]
  );
  const dependents = useMemo(() => (node ? dependentsOf(graph, node.id) : []), [graph, node]);
  const targets = useMemo(() => (node ? connectableTargets(graph, node.id) : []), [graph, node]);
  const nodeIssues = useMemo(
    () => (node ? report.issues.filter((i) => i.nodeIds.includes(node.id)) : []),
    [report, node]
  );

  if (!node) {
    return (
      <div className="p-4">
        <EmptyState
          compact
          icon={MousePointerSquareDashed}
          title="Nothing selected"
          description="Select a step to edit its properties."
        />
      </div>
    );
  }

  const meta = NODE_TYPES[node.kind];
  const Icon = meta.icon;
  const byId = (id: string) => graph.nodes.find((n) => n.id === id);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center gap-2.5 border-b p-4">
        <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <Icon className="size-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm font-semibold text-foreground">{node.name}</h2>
          <p className="truncate text-xs text-muted-foreground">{meta.label}</p>
        </div>
      </header>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-4">
        {nodeIssues.length > 0 ? (
          <Alert variant={nodeIssues.some((i) => i.severity === "error") ? "error" : "warning"}>
            <ul className="space-y-1">
              {nodeIssues.map((issue) => (
                <li key={`${issue.rule}-${issue.message}`}>{issue.message}</li>
              ))}
            </ul>
          </Alert>
        ) : null}

        <PropertiesPanel node={node} />

        <section aria-labelledby="inspector-connections" className="space-y-3 border-t pt-4">
          <h4 id="inspector-connections" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Connections
          </h4>

          <div className="space-y-1">
            <p className="px-2 text-xs text-muted-foreground">Runs after</p>
            {dependencies.length === 0 ? (
              <p className="px-2 py-1.5 text-sm text-muted-foreground/70">Nothing — this is a starting step.</p>
            ) : (
              <ul>
                {dependencies.map((id) => {
                  const source = byId(id);
                  return source ? (
                    <ConnectionRow
                      key={id}
                      node={source}
                      edgeId={`edg_${id}__${node.id}`}
                      label="Remove dependency on"
                    />
                  ) : null;
                })}
              </ul>
            )}
          </div>

          <div className="space-y-1">
            <p className="px-2 text-xs text-muted-foreground">Runs before</p>
            {dependents.length === 0 ? (
              <p className="px-2 py-1.5 text-sm text-muted-foreground/70">Nothing — this is a final step.</p>
            ) : (
              <ul>
                {dependents.map((id) => {
                  const target = byId(id);
                  return target ? (
                    <ConnectionRow
                      key={id}
                      node={target}
                      edgeId={`edg_${node.id}__${id}`}
                      label="Remove connection to"
                    />
                  ) : null;
                })}
              </ul>
            )}
          </div>

          {targets.length > 0 ? (
            <div className="flex items-end gap-2">
              <Field label="Connect to" className="min-w-0 flex-1">
                {({ id }) => (
                  <Select
                    id={id}
                    className="h-9"
                    value={pendingTarget}
                    onChange={(event) => setPendingTarget(event.target.value)}
                  >
                    <option value="">Choose a step…</option>
                    {targets.map((target) => (
                      <option key={target.id} value={target.id}>
                        {target.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Button
                variant="outline"
                size="sm"
                className="h-9"
                disabled={!pendingTarget}
                onClick={() => {
                  if (connectNodes(node.id, pendingTarget)) setPendingTarget("");
                }}
              >
                Connect
              </Button>
            </div>
          ) : null}
        </section>

        <section aria-labelledby="inspector-platform" className="space-y-2 border-t pt-4">
          <h4 id="inspector-platform" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Platform
          </h4>
          <p className="text-xs text-muted-foreground">
            Set by the platform when a workflow runs. Read-only here.
          </p>
          <dl className="space-y-1.5 text-sm">
            <div className="flex items-center justify-between gap-2">
              <dt className="text-muted-foreground">Step id</dt>
              <dd className="truncate font-mono text-xs text-foreground">{node.id}</dd>
            </div>
            <div className="flex items-center justify-between gap-2">
              <dt className="text-muted-foreground">Run status</dt>
              <dd className="text-foreground">Not run</dd>
            </div>
            <div className="flex items-center justify-between gap-2">
              <dt className="text-muted-foreground">Execution group</dt>
              <dd className="text-foreground">—</dd>
            </div>
          </dl>
        </section>
      </div>

      <footer className="flex gap-2 border-t p-3">
        <Button variant="outline" size="sm" className="flex-1" onClick={() => duplicateNode(node.id)}>
          <Copy className="size-3.5" aria-hidden="true" />
          Duplicate
        </Button>
        <Button variant="outline" size="sm" className="flex-1" onClick={() => deleteNode(node.id)}>
          <Trash2 className="size-3.5" aria-hidden="true" />
          Delete
        </Button>
      </footer>
    </div>
  );
}
