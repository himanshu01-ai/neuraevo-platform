"use client";

import { motion } from "framer-motion";
import { MousePointerSquareDashed, SquareArrowOutUpRight } from "lucide-react";
import { LANGUAGE_LABEL } from "@/services/memory";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { formatBytes, formatDate } from "@/utils/format";
import { useMemoryDetail } from "../hooks/use-memory";
import { collectionLabel } from "../models/collections";
import { MEMORY_KIND_META } from "../models/memory-kinds";
import { MemoryStatusBadge, MemoryTypeBadge } from "../components/memory-badges";
import { KnowledgeViewerLoading } from "../components/memory-states";
import { cn } from "@/lib/utils";

export interface KnowledgeViewerProps {
  memoryId: string | null;
  className?: string;
}

/**
 * The middle column: the memory itself, read as it was written.
 *
 * The content renders in a `<pre>` with wrapping rather than as prose. A memory
 * holds procedures, schemas and templates whose line breaks and indentation
 * carry meaning — collapsing whitespace would quietly corrupt a runnable command
 * into a sentence. It stays selectable, wraps at the panel edge, and never
 * scrolls the page sideways.
 *
 * The panel cross-fades on selection, keyed by memory, so switching reads as a
 * change of subject rather than a reflow. Reduced motion collapses it to a cut.
 */
export function KnowledgeViewer({ memoryId, className }: KnowledgeViewerProps) {
  const query = useMemoryDetail(memoryId);

  if (memoryId === null) {
    return (
      <EmptyState
        icon={MousePointerSquareDashed}
        title="No memory selected"
        description="Pick something from the tree to read it."
        className={className}
      />
    );
  }

  if (query.isPending) return <KnowledgeViewerLoading className={className} />;

  if (query.isError || !query.data) {
    return (
      <ErrorState
        title="Couldn't load this memory"
        description="This memory doesn't exist, or it was removed."
        onRetry={() => void query.refetch()}
        className={className}
      />
    );
  }

  const memory = query.data;
  const kind = MEMORY_KIND_META[memory.kind];
  const KindIcon = kind.icon;

  return (
    <motion.article
      key={memory.id}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
      className={cn("space-y-4", className)}
    >
      <header className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
              <KindIcon className="size-4" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <h2 className="text-md font-semibold leading-tight text-foreground">{memory.title}</h2>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {kind.label} · {collectionLabel(memory.collection, memory.customCollection)}
              </p>
            </div>
          </div>

          <Button variant="outline" size="sm" href={`/workspace/memory/${memory.id}`} className="shrink-0">
            <SquareArrowOutUpRight className="size-4" aria-hidden="true" />
            Open
          </Button>
        </div>

        <p className="text-sm leading-relaxed text-muted-foreground">{memory.summary}</p>

        <div className="flex flex-wrap items-center gap-1.5">
          <MemoryTypeBadge memoryType={memory.memoryType} />
          <MemoryStatusBadge status={memory.status} />
          <Badge variant="outline">{LANGUAGE_LABEL[memory.language]}</Badge>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Avatar name={memory.owner.employeeName} className="size-4 text-[0.5rem]" />
            <span className="sr-only">Owner: </span>
            {memory.owner.employeeName}
          </span>
          <span>
            <span className="sr-only">Created: </span>Created {formatDate(memory.createdAt)}
          </span>
          <span>
            <span className="sr-only">Updated: </span>Updated {formatDate(memory.updatedAt)}
          </span>
          <span className="tabular-nums">{formatBytes(memory.sizeBytes)}</span>
        </div>
      </header>

      <div className="rounded-md border bg-muted/40 p-4">
        <h3 className="sr-only">Memory content</h3>
        {/* Whitespace is content here — a procedure's indentation is the procedure. */}
        <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-foreground">
          {memory.content}
        </pre>
      </div>

      {memory.tags.length > 0 ? (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tags</h3>
          <ul className="mt-2 flex flex-wrap items-center gap-1.5">
            {memory.tags.map((tag) => (
              <li key={tag}>
                <Badge variant="default">#{tag}</Badge>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </motion.article>
  );
}
