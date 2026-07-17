"use client";

import { useCallback, useId, useRef, useState, type DragEvent } from "react";
import { CircleCheck, TriangleAlert, Upload, X } from "lucide-react";
import {
  MAX_IMPORT_BYTES,
  SUPPORTED_IMPORT_TYPES,
  memoryService,
  type ImportCandidate,
  type ImportSummary,
} from "@/services/memory";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatBytes } from "@/utils/format";
import { collectionLabel } from "../models/collections";
import { MEMORY_KIND_META } from "../models/memory-kinds";
import { cn } from "@/lib/utils";

/**
 * Bringing knowledge in.
 *
 * **Nothing is uploaded, and nothing is read.** The file's bytes are never
 * touched: validation works from the name and size a drop event already gives
 * us, and the preview says plainly that the content isn't read yet. That's the
 * honest shape for this sprint — a preview of text we hadn't parsed would be
 * text we invented.
 *
 * The drop zone is a real `<input type="file">` behind a label, not a div with a
 * click handler. That's what makes it keyboard-reachable, announceable, and able
 * to open the system file picker at all; the drag handlers are an enhancement on
 * top, not the mechanism.
 */
export function ImportPanel({ className }: { className?: string }) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  const [isOver, setIsOver] = useState(false);
  const [candidates, setCandidates] = useState<ImportCandidate[]>([]);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  const stage = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setIsChecking(true);
    setSummary(null);

    // Only the name and the size cross this boundary — the file itself is never
    // opened, so there is nothing here that could leave the machine.
    const staged = [...files].map((file) => ({ name: file.name, sizeBytes: file.size }));
    const checked = await memoryService.validateImport(staged);
    setCandidates(checked);
    setIsChecking(false);
  }, []);

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsOver(false);
    void stage(event.dataTransfer.files);
  };

  const handleSummarise = async () => {
    setSummary(await memoryService.summariseImport(candidates));
  };

  const clear = () => {
    setCandidates([]);
    setSummary(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const accepted = candidates.filter((c) => !c.issues.some((i) => i.level === "error"));

  return (
    <div className={cn("space-y-4", className)}>
      <label
        htmlFor={inputId}
        onDragOver={(event) => {
          event.preventDefault();
          setIsOver(true);
        }}
        onDragLeave={() => setIsOver(false)}
        onDrop={handleDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors",
          "focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background",
          isOver ? "border-primary bg-primary/5" : "border-border hover:border-primary/40"
        )}
      >
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          multiple
          accept={SUPPORTED_IMPORT_TYPES.map((t) => `.${t}`).join(",")}
          onChange={(event) => void stage(event.target.files)}
          className="sr-only"
        />

        <span className="inline-flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Upload className="size-5" aria-hidden="true" />
        </span>
        <span className="text-sm font-medium text-foreground">
          Drop files here, or choose them
        </span>
        <span className="text-xs text-muted-foreground">
          {SUPPORTED_IMPORT_TYPES.join(", ")} · up to {formatBytes(MAX_IMPORT_BYTES)} each
        </span>
      </label>

      <Alert variant="info">
        Nothing is uploaded in this sprint. Files are checked and previewed here; the platform is what
        reads them.
      </Alert>

      {isChecking ? (
        <p role="status" className="text-sm text-muted-foreground">
          Checking files…
        </p>
      ) : null}

      {candidates.length > 0 ? (
        <section>
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-foreground">
              Import preview
              <span className="ml-2 font-normal text-muted-foreground">
                {accepted.length} of {candidates.length} would import
              </span>
            </h3>
            <Button variant="ghost" size="sm" onClick={clear}>
              <X className="size-4" aria-hidden="true" />
              Clear
            </Button>
          </div>

          <ul className="mt-3 space-y-2">
            {candidates.map((candidate) => {
              const hasError = candidate.issues.some((i) => i.level === "error");
              const KindIcon = MEMORY_KIND_META[candidate.preview.kind].icon;

              return (
                <li
                  key={candidate.id}
                  className={cn(
                    "rounded-md border bg-card p-3",
                    hasError ? "border-destructive/30" : "border-border"
                  )}
                >
                  <div className="flex items-start gap-3">
                    <span
                      className={cn(
                        "inline-flex size-8 shrink-0 items-center justify-center rounded-md",
                        hasError ? "bg-destructive/10 text-destructive" : "bg-muted text-muted-foreground"
                      )}
                    >
                      {hasError ? (
                        <TriangleAlert className="size-4" aria-hidden="true" />
                      ) : (
                        <KindIcon className="size-4" aria-hidden="true" />
                      )}
                    </span>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <p className="min-w-0 truncate font-mono text-sm text-foreground">
                          {candidate.name}
                        </p>
                        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                          {formatBytes(candidate.sizeBytes)}
                        </span>
                      </div>

                      {candidate.issues.length > 0 ? (
                        <ul className="mt-1.5 space-y-1">
                          {candidate.issues.map((issue) => (
                            <li
                              key={issue.message}
                              className={cn(
                                "text-xs",
                                issue.level === "error" ? "text-destructive" : "text-warning"
                              )}
                            >
                              {/* The level is said, not just coloured. */}
                              <span className="sr-only">
                                {issue.level === "error" ? "Error: " : "Warning: "}
                              </span>
                              {issue.message}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-1.5 flex items-center gap-1.5 text-xs text-success">
                          <CircleCheck className="size-3.5 shrink-0" aria-hidden="true" />
                          Ready to import
                        </p>
                      )}

                      {!hasError ? (
                        <dl className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 border-t pt-2 text-xs text-muted-foreground">
                          <div className="flex items-center gap-1.5">
                            <dt className="sr-only">Title</dt>
                            <dd className="font-medium text-foreground">{candidate.preview.title}</dd>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <dt className="sr-only">Type</dt>
                            <dd>
                              <Badge variant="outline">
                                {MEMORY_KIND_META[candidate.preview.kind].label}
                              </Badge>
                            </dd>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <dt className="sr-only">Collection</dt>
                            <dd>{collectionLabel(candidate.preview.collection, "")}</dd>
                          </div>
                        </dl>
                      ) : null}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>

          <div className="mt-3 flex items-center gap-2">
            <Button size="sm" onClick={() => void handleSummarise()} disabled={candidates.length === 0}>
              Review import
            </Button>
          </div>
        </section>
      ) : null}

      {summary ? (
        <section aria-live="polite">
          <h3 className="text-sm font-semibold text-foreground">Import summary</h3>
          <dl className="mt-2 grid grid-cols-3 gap-3">
            <div className="rounded-md border bg-card p-3">
              <dt className="text-xs text-muted-foreground">Would import</dt>
              <dd className="mt-0.5 text-lg font-semibold tabular-nums text-foreground">
                {summary.accepted}
              </dd>
            </div>
            <div className="rounded-md border bg-card p-3">
              <dt className="text-xs text-muted-foreground">Rejected</dt>
              <dd className="mt-0.5 text-lg font-semibold tabular-nums text-foreground">
                {summary.rejected}
              </dd>
            </div>
            <div className="rounded-md border bg-card p-3">
              <dt className="text-xs text-muted-foreground">Total size</dt>
              <dd className="mt-0.5 text-lg font-semibold tabular-nums text-foreground">
                {formatBytes(summary.totalBytes)}
              </dd>
            </div>
          </dl>
          <p className="mt-2 text-sm text-muted-foreground">{summary.note}</p>
        </section>
      ) : null}
    </div>
  );
}
