"use client";

import { useState } from "react";
import { FileStack } from "lucide-react";
import type { Artifact } from "@/services/tasks";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { useTaskArtifacts } from "../hooks/use-tasks";
import { ArtifactCard } from "./artifact-card";
import { cn } from "@/lib/utils";

export interface ArtifactListProps {
  taskId: string;
  className?: string;
}

/** Everything a run produced, newest first. */
export function ArtifactList({ taskId, className }: ArtifactListProps) {
  const query = useTaskArtifacts(taskId);
  const [notice, setNotice] = useState<string | null>(null);

  if (query.isPending) return <LoadingState rows={3} className={className} />;

  if (query.isError) {
    return (
      <ErrorState
        compact
        title="Couldn't load artifacts"
        description="What this task produced couldn't be loaded."
        onRetry={() => void query.refetch()}
        className={className}
      />
    );
  }

  if (query.data.length === 0) {
    return (
      <EmptyState
        compact
        icon={FileStack}
        title="Nothing produced yet"
        description="Documents, code and reports from this run will show up here."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      {notice ? <Alert variant="info">{notice}</Alert> : null}

      <div className="grid gap-2 lg:grid-cols-2">
        {query.data.map((artifact: Artifact) => (
          <ArtifactCard
            key={artifact.id}
            artifact={artifact}
            onDownload={(a) =>
              // Saying so is the honest outcome: there's no file behind a fixture,
              // and handing over an empty one would be worse than declining.
              setNotice(`“${a.name}” is mock data — there's no file to download until the platform serves one.`)
            }
          />
        ))}
      </div>
    </div>
  );
}
