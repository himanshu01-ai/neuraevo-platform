"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { MousePointerSquareDashed } from "lucide-react";
import {
  LANGUAGE_LABEL,
  RELATIONSHIP_LABEL,
  neighboursOf,
  type KnowledgeGraph,
  type MemoryDetail,
} from "@/services/memory";
import { useMemoryStore } from "@/store/memory";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Progress } from "@/components/ui/progress";
import { formatBytes, formatDate, formatDateTime, formatPercent } from "@/utils/format";
import { collectionLabel } from "../models/collections";
import { GRAPH_NODE_META } from "../models/graph-nodes";
import { MEMORY_KIND_META } from "../models/memory-kinds";
import { MemoryStatusBadge, MemoryTypeBadge } from "./memory-badges";
import { cn } from "@/lib/utils";

export interface MemoryInspectorProps {
  memory: MemoryDetail | null;
  /** Used for the relationships section. Omit where the graph isn't loaded. */
  graph?: KnowledgeGraph;
  className?: string;
}

/** A labelled row in the metadata table. */
function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5">
      <dt className="shrink-0 text-xs text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-right text-xs font-medium text-foreground">{children}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t pt-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      <div className="mt-2">{children}</div>
    </section>
  );
}

/**
 * The right-hand column: everything about the selected memory that isn't the
 * memory itself.
 *
 * Metadata, relationships, collections, tags, usage, history and links, in one
 * scrollable column. The relationships list is what makes the knowledge graph
 * usable by keyboard at all — the SVG edges are decorative, so this states each
 * association in words, names the relationship, and lets you jump to the other
 * end.
 *
 * Importance is the backend's `importance_score`, shown as the 0–1 ratio it is
 * (formatted as a percentage) rather than a rating the UI invented.
 */
export function MemoryInspector({ memory, graph, className }: MemoryInspectorProps) {
  const selectGraphNode = useMemoryStore((s) => s.selectGraphNode);

  if (!memory) {
    return (
      <EmptyState
        compact
        icon={MousePointerSquareDashed}
        title="Nothing selected"
        description="Pick a memory to inspect it."
        className={className}
      />
    );
  }

  const kind = MEMORY_KIND_META[memory.kind];
  const anchor = graph ? (graph.nodes.find((n) => n.memoryId === memory.id) ?? null) : null;
  const neighbours = graph && anchor ? neighboursOf(graph, anchor.id) : [];

  return (
    <motion.div
      key={memory.id}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className={cn("space-y-4", className)}
    >
      <div>
        <h2 className="truncate text-sm font-semibold text-foreground">{memory.title}</h2>
        <p className="truncate text-xs text-muted-foreground">{kind.label}</p>
      </div>

      <Section title="Metadata">
        <dl className="divide-y">
          <Row label="Type">{kind.label}</Row>
          <Row label="Retention">
            <MemoryTypeBadge memoryType={memory.memoryType} />
          </Row>
          <Row label="Status">
            <MemoryStatusBadge status={memory.status} />
          </Row>
          <Row label="Language">{LANGUAGE_LABEL[memory.language]}</Row>
          <Row label="Size">
            <span className="tabular-nums">{formatBytes(memory.sizeBytes)}</span>
          </Row>
          <Row label="Created">
            <time dateTime={memory.createdAt} className="tabular-nums">
              {formatDate(memory.createdAt)}
            </time>
          </Row>
          <Row label="Updated">
            <time dateTime={memory.updatedAt} className="tabular-nums">
              {formatDate(memory.updatedAt)}
            </time>
          </Row>
        </dl>

        <div className="mt-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-muted-foreground">Importance</span>
            <span className="text-xs font-medium tabular-nums text-foreground">
              {formatPercent(memory.importanceScore)}
            </span>
          </div>
          <Progress
            value={memory.importanceScore * 100}
            label={`Importance of ${memory.title}`}
            className="mt-1.5"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            The platform&apos;s own score, from 0 to 1.
          </p>
        </div>
      </Section>

      <Section title="Owner">
        <p className="flex items-center gap-2 text-sm">
          <Avatar name={memory.owner.employeeName} className="size-5 text-[0.625rem]" />
          <Link
            href={`/workspace/employees/${memory.owner.employeeId}`}
            className="min-w-0 truncate rounded-sm text-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {memory.owner.employeeName}
          </Link>
        </p>
      </Section>

      <Section title="Collection">
        <Badge variant="outline">{collectionLabel(memory.collection, memory.customCollection)}</Badge>
      </Section>

      <Section title="Tags">
        {memory.tags.length === 0 ? (
          <p className="text-sm text-muted-foreground">No tags.</p>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {memory.tags.map((tag) => (
              <li key={tag}>
                <Badge variant="default">#{tag}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Relationships">
        {neighbours.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {graph ? "Nothing is connected to this yet." : "Open the graph to see what this touches."}
          </p>
        ) : (
          <ul className="space-y-1">
            {neighbours.map(({ node, edge, isOutgoing }) => {
              const meta = GRAPH_NODE_META[node.kind];
              const Icon = meta.icon;
              return (
                <li key={edge.id}>
                  <button
                    type="button"
                    onClick={() => selectGraphNode(node.id)}
                    className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-foreground">{node.name}</span>
                      {/* The direction is said, not implied by an arrow nobody can focus. */}
                      <span className="block truncate text-xs text-muted-foreground">
                        {isOutgoing ? "" : "is "}
                        {RELATIONSHIP_LABEL[edge.relationship]}
                        {isOutgoing ? "" : " this"} · {meta.label}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      <Section title="Linked employees">
        {memory.linkedEmployees.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nobody else uses this.</p>
        ) : (
          <ul className="space-y-1">
            {memory.linkedEmployees.map((link) => (
              <li key={link.employeeId}>
                <Link
                  href={`/workspace/employees/${link.employeeId}`}
                  className="flex items-center gap-2 rounded-sm px-2 py-1 text-sm text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Avatar name={link.employeeName} className="size-4 text-[0.5rem]" />
                  <span className="min-w-0 truncate">{link.employeeName}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Linked workflows">
        {memory.linkedWorkflows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No workflow reads this.</p>
        ) : (
          <ul className="space-y-1">
            {memory.linkedWorkflows.map((link) => (
              <li key={link.workflowId}>
                <Link
                  href={`/workspace/workflows/${link.workflowId}`}
                  className="block truncate rounded-sm px-2 py-1 text-sm text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {link.workflowName}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Usage">
        <dl className="divide-y">
          <Row label="Recalled">
            <span className="tabular-nums">
              {memory.usage.recallCount} {memory.usage.recallCount === 1 ? "time" : "times"}
            </span>
          </Row>
          <Row label="Last recalled">
            {memory.usage.lastRecalledAt ? (
              <time dateTime={memory.usage.lastRecalledAt} className="tabular-nums">
                {formatDateTime(memory.usage.lastRecalledAt)}
              </time>
            ) : (
              "Never"
            )}
          </Row>
        </dl>
        <p className="mt-2 text-xs text-muted-foreground">{memory.usage.note}</p>
      </Section>
    </motion.div>
  );
}
