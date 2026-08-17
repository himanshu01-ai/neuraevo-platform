"use client";

import Link from "next/link";
import { Brain, ChartNoAxesCombined, Folder, Import, Search, Share2 } from "lucide-react";
import { EMPTY_SEARCH } from "@/services/memory";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Shimmer } from "@/components/ui/shimmer";
import { Panel } from "@/features/workspace/panels/panel";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Reveal } from "@/components/motion/reveal";
import { formatBytes, formatPercent } from "@/utils/format";
import { useCollections, useMemoryInsights, useMemoryList } from "../hooks/use-memory";
import { DistributionList } from "../insights/distribution-list";
import { MemoryTimeline } from "../timeline/memory-timeline";
import { COLLECTION_META } from "../models/collections";
import { MemoryCard } from "./memory-card";
import { MemoryEmptyState } from "./memory-states";

const LINKS = [
  { href: "/workspace/memory", label: "Browse knowledge", icon: Brain },
  { href: "/workspace/memory/search", label: "Search", icon: Search },
  { href: "/workspace/memory/collections", label: "Collections", icon: Folder },
  { href: "/workspace/memory/graph", label: "Knowledge graph", icon: Share2 },
  { href: "/workspace/memory/insights", label: "Insights", icon: ChartNoAxesCombined },
  { href: "/workspace/memory/documents", label: "Import", icon: Import },
];

/**
 * The memory landing: how much is known, where it lives, and what changed.
 *
 * A dashboard, not the workspace — this answers "what's in here" at a glance and
 * hands you off. The browser at `/workspace/memory` is where you actually read
 * and organise, and the sidebar points there because that's the job.
 *
 * The headline counts mirror the frozen `MemoryStatsResponse` field for field.
 */
export function MemoryDashboard() {
  const insights = useMemoryInsights();
  const collections = useCollections();
  // The most important knowledge, as the platform scores it — not as we rank it.
  const important = useMemoryList({ ...EMPTY_SEARCH, minImportance: 0.75 });

  if (insights.isError) {
    return (
      <WorkspaceContent>
        <ErrorState
          title="Couldn't load memory"
          description="The knowledge summary couldn't be loaded. Try again in a moment."
          onRetry={() => void insights.refetch()}
        />
      </WorkspaceContent>
    );
  }

  const totals = insights.data?.totals;

  const stats = [
    { label: "Memories", value: totals ? String(totals.totalMemories) : "—" },
    { label: "Permanent", value: totals ? String(totals.permanentCount) : "—" },
    { label: "Working", value: totals ? String(totals.workingCount) : "—" },
    { label: "Learned", value: totals ? String(totals.learnedCount) : "—" },
    {
      label: "Avg. importance",
      value: totals ? formatPercent(totals.averageImportanceScore) : "—",
    },
    {
      label: "Total size",
      value: insights.data ? formatBytes(insights.data.totalSizeBytes) : "—",
    },
  ];

  return (
    <WorkspaceContent>
      <Reveal>
        <WorkspaceHeader
          title="Memory"
          description="What your AI employees know, at a glance."
          actions={
            <Button href="/workspace/memory">
              <Brain className="size-4" aria-hidden="true" />
              Browse knowledge
            </Button>
          }
        />
      </Reveal>

      <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-lg border bg-card p-3 shadow-sm">
            <dt className="truncate text-xs text-muted-foreground">{stat.label}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-foreground">
              {insights.isPending ? <Shimmer className="h-6 w-10" /> : stat.value}
            </dd>
          </div>
        ))}
      </dl>

      <nav aria-label="Memory sections" className="mt-4">
        <ul className="flex flex-wrap gap-2">
          {LINKS.map(({ href, label, icon: Icon }) => (
            <li key={href}>
              <Link
                href={href}
                className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1.5 text-xs font-medium text-foreground shadow-sm transition-colors hover:border-primary/40 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Icon className="size-3.5" aria-hidden="true" />
                {label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="min-w-0 space-y-6 lg:col-span-2">
          <Reveal>
            <Panel
              title="Most important"
              description="What the platform scores at 75% or above."
              loading={important.isPending}
            >
              {important.data && important.data.length > 0 ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  {important.data.slice(0, 4).map((memory) => (
                    <MemoryCard key={memory.id} memory={memory} />
                  ))}
                </div>
              ) : (
                <MemoryEmptyState
                  compact
                  title="Nothing scored that high yet"
                  description="Importance is the platform's own score."
                  showActions={false}
                />
              )}
            </Panel>
          </Reveal>

          <Reveal delay={0.05}>
            <Panel title="Collections" description="Where the knowledge lives." loading={collections.isPending}>
              {collections.data ? (
                <ul className="grid gap-2 sm:grid-cols-2">
                  {collections.data.map((entry) => {
                    const Icon = COLLECTION_META[entry.collection].icon;
                    return (
                      <li key={entry.collection}>
                        <Link
                          href="/workspace/memory/collections"
                          className="flex items-center gap-2.5 rounded-md border bg-background p-2.5 transition-colors hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-sm bg-muted text-muted-foreground">
                            <Icon className="size-3.5" aria-hidden="true" />
                          </span>
                          <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                            {entry.name}
                          </span>
                          <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                            {entry.count}
                          </span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              ) : null}
            </Panel>
          </Reveal>
        </div>

        <div className="min-w-0 space-y-6">
          <Reveal delay={0.05}>
            <Panel
              title="Memory distribution"
              description="By retention."
              loading={insights.isPending}
            >
              {insights.data ? <DistributionList slices={insights.data.distribution} /> : null}
            </Panel>
          </Reveal>

          <Reveal delay={0.1}>
            <Panel title="Recent changes" description="Newest first.">
              <MemoryTimeline memoryId={null} limit={6} showMemory />
            </Panel>
          </Reveal>
        </div>
      </div>
    </WorkspaceContent>
  );
}
