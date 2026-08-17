"use client";

import { memo } from "react";
import { Brain } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { WidgetShell } from "../components/widget-shell";
import { useMemorySummary } from "../hooks/use-dashboard";

/** Memory Summary — the total and its category breakdown, as carried counts. */
export const MemoryWidget = memo(function MemoryWidget() {
  const query = useMemorySummary();
  const memory = query.data;

  return (
    <WidgetShell
      title="Memory"
      description="What your AI employee remembers."
      href="/workspace/memory"
      isLoading={query.isPending}
      isError={query.isError}
      isEmpty={!memory || memory.total === 0}
      isRefreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
      empty={
        <EmptyState
          compact
          icon={Brain}
          title="Nothing remembered yet"
          description="Memories build up as you work together."
          action={
            <Button variant="outline" size="sm" href="/workspace/memory">
              Open memory
            </Button>
          }
        />
      }
    >
      {memory ? (
        <div className="space-y-4">
          <div>
            <p className="text-2xl font-semibold tracking-tight text-foreground">{memory.total}</p>
            <p className="text-xs text-muted-foreground">memories stored</p>
          </div>
          <ul aria-label="Memory categories" className="space-y-2">
            {memory.categories.map((category) => (
              <li key={category.category} className="flex items-center justify-between gap-3 text-sm">
                <span className="truncate text-muted-foreground">{category.category}</span>
                <span className="shrink-0 font-medium text-foreground">{category.count}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </WidgetShell>
  );
});
