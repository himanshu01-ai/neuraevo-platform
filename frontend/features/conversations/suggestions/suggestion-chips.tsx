"use client";

import type { Suggestion } from "@/services/conversations";
import { SUGGESTION_KIND_META } from "../models/message-kinds";
import { cn } from "@/lib/utils";

export interface SuggestionChipsProps {
  suggestions: Suggestion[];
  /** Picking a chip only writes into the draft — it never sends. */
  onPick: (suggestion: Suggestion) => void;
  className?: string;
}

/**
 * The chips above the composer: suggested prompts, recent tasks, workflows,
 * memories, employees and quick actions, each marked by its kind's icon. One
 * horizontal row that scrolls rather than wraps, so the composer never sinks.
 */
export function SuggestionChips({ suggestions, onPick, className }: SuggestionChipsProps) {
  if (suggestions.length === 0) return null;

  return (
    <ul
      className={cn("flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:thin]", className)}
      aria-label="Suggestions"
    >
      {suggestions.map((suggestion) => {
        const meta = SUGGESTION_KIND_META[suggestion.kind];
        const Icon = meta.icon;
        return (
          <li key={suggestion.id} className="shrink-0">
            <button
              type="button"
              onClick={() => onPick(suggestion)}
              title={meta.label}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1.5 text-xs text-foreground transition-colors",
                "hover:border-primary/40 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              )}
            >
              <Icon className="size-3.5 text-primary" aria-hidden="true" />
              <span className="sr-only">{meta.label}: </span>
              {suggestion.label}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
