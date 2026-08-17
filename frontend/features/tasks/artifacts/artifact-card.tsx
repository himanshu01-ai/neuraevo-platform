"use client";

import { memo, useState } from "react";
import { ChevronDown, Download, Eye } from "lucide-react";
import type { Artifact } from "@/services/tasks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ARTIFACT_META } from "../models/artifact-kinds";
import { cn } from "@/lib/utils";

export interface ArtifactCardProps {
  artifact: Artifact;
  onDownload: (artifact: Artifact) => void;
}

/**
 * One thing a run produced: what it is, how big, and what's inside.
 *
 * The preview expands in place rather than opening a dialog — these are short
 * excerpts, and a modal for six lines of text is a ceremony. It's a real
 * disclosure (`aria-expanded` on a button that controls the panel), so it
 * behaves for a keyboard and a screen reader alike.
 *
 * Download is deliberately inert. These artifacts are fixtures; there is no file
 * behind them, so the button reports that rather than handing over an empty one.
 * Sprint 17.8 wires it to whatever the platform serves.
 */
export const ArtifactCard = memo(function ArtifactCard({ artifact, onDownload }: ArtifactCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const meta = ARTIFACT_META[artifact.kind];
  const Icon = meta.icon;
  const panelId = `artifact-preview-${artifact.id}`;

  return (
    <div className="rounded-lg border bg-card shadow-sm transition-colors hover:border-primary/30">
      <div className="flex items-start gap-3 p-3">
        <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <Icon className="size-4" aria-hidden="true" />
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <p className="min-w-0 truncate font-mono text-sm font-medium text-foreground">{artifact.name}</p>
            <Badge variant="outline" className="shrink-0">
              {meta.label}
            </Badge>
          </div>
          <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{artifact.description}</p>

          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="text-xs tabular-nums text-muted-foreground">{artifact.size}</span>

            {artifact.preview !== null ? (
              <Button
                variant="ghost"
                size="sm"
                className="h-7"
                onClick={() => setIsOpen((open) => !open)}
                aria-expanded={isOpen}
                aria-controls={panelId}
              >
                <Eye className="size-3.5" aria-hidden="true" />
                Preview
                <ChevronDown
                  className={cn("size-3.5 transition-transform", isOpen && "rotate-180")}
                  aria-hidden="true"
                />
              </Button>
            ) : null}

            <Button variant="ghost" size="sm" className="h-7" onClick={() => onDownload(artifact)}>
              <Download className="size-3.5" aria-hidden="true" />
              Download
            </Button>
          </div>
        </div>
      </div>

      {isOpen && artifact.preview !== null ? (
        <div id={panelId} className="border-t bg-muted/40 p-3">
          <pre
            className={cn(
              "max-h-48 overflow-auto whitespace-pre-wrap break-words text-xs leading-relaxed text-foreground",
              meta.isMonospace ? "font-mono" : "font-sans"
            )}
          >
            {artifact.preview}
          </pre>
        </div>
      ) : null}
    </div>
  );
});
