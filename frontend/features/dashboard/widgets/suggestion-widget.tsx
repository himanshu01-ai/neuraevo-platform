"use client";

import { memo } from "react";
import { Sparkles } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { WorkspaceCard } from "@/features/workspace/panels/workspace-card";
import { WidgetShell } from "../components/widget-shell";
import { Shimmer } from "../components/widget-skeleton";
import { useSuggestions } from "../hooks/use-dashboard";

const GRID = "grid gap-4 sm:grid-cols-3";

/**
 * Suggested Actions. Every card is here because a rule in `models/suggestions`
 * matched a plain fact about the workspace — nothing is generated or ranked.
 */
export const SuggestionWidget = memo(function SuggestionWidget() {
  const { query, suggestions } = useSuggestions();

  return (
    <WidgetShell
      variant="bare"
      title="Suggested actions"
      description="Next steps based on how your workspace is set up."
      isLoading={query.isPending}
      isError={query.isError}
      isEmpty={suggestions.length === 0}
      isRefreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
      loading={
        <div role="status" aria-label="Loading suggestions" className={GRID}>
          {Array.from({ length: 3 }).map((_, i) => (
            <Shimmer key={i} className="h-36" />
          ))}
        </div>
      }
      empty={
        <EmptyState
          icon={Sparkles}
          title="Nothing to suggest"
          description="Your workspace is set up. Suggestions return when there's something worth doing."
        />
      }
    >
      <div className={GRID}>
        {suggestions.map((suggestion) => (
          <WorkspaceCard
            key={suggestion.id}
            title={suggestion.title}
            description={suggestion.description}
            icon={suggestion.icon}
            href={suggestion.href}
          />
        ))}
      </div>
    </WidgetShell>
  );
});
