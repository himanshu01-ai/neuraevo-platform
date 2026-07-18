"use client";

import type { ArtifactPayload } from "@/services/conversations";
import { Badge } from "@/components/ui/badge";
import { ARTIFACT_KIND_META } from "../models/message-kinds";
import { cn } from "@/lib/utils";

/**
 * A generated artifact in the thread: name, kind, size, and an inline mock
 * preview. `code` previews render monospaced; nothing opens, downloads, or
 * executes — the card is the whole artifact for this sprint.
 */
export function ArtifactCard({ artifact, className }: { artifact: ArtifactPayload; className?: string }) {
  const meta = ARTIFACT_KIND_META[artifact.kind];
  const Icon = meta.icon;

  return (
    <section aria-label={`${meta.label}: ${artifact.name}`} className={cn("rounded-lg border bg-card shadow-sm", className)}>
      <div className="flex items-center justify-between gap-2 border-b p-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Icon className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h4 className="truncate text-sm font-semibold text-foreground">{artifact.name}</h4>
            <p className="text-xs text-muted-foreground">{artifact.size}</p>
          </div>
        </div>
        <Badge variant="primary" className="shrink-0">
          {meta.label}
        </Badge>
      </div>
      {artifact.preview ? (
        <pre
          className={cn(
            "max-h-48 overflow-auto whitespace-pre-wrap break-words p-3 text-xs text-muted-foreground",
            artifact.kind === "code" ? "font-mono" : "font-sans"
          )}
        >
          {artifact.preview}
        </pre>
      ) : (
        <p className="p-3 text-xs text-muted-foreground">No inline preview for this artifact.</p>
      )}
    </section>
  );
}
