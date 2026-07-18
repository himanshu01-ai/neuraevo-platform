"use client";

import { ErrorState } from "@/components/ui/error-state";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { Reveal } from "@/components/motion/reveal";
import { useTeamActivity } from "../hooks/use-collaboration";
import { ActivityFeed } from "../activity/activity-feed";
import { CollaborationHeader } from "./collaboration-header";
import { FeedLoading } from "./collaboration-loading";

/**
 * The Team Activity feed: everyone's actions — you, your AI employees, and
 * teammates — in one timeline. Same feed component as the personal Activity
 * screen, aimed at the whole workspace.
 */
export function TeamActivityScreen() {
  const team = useTeamActivity();

  return (
    <WorkspaceContent>
      <Reveal>
        <CollaborationHeader
          title="Team activity"
          description="Everything happening across your workspace — people and AI employees alike."
        />
      </Reveal>

      <div className="mt-4 max-w-3xl">
        {team.isError ? (
          <ErrorState
            title="Couldn't load team activity"
            description="The team feed couldn't be loaded. Try again in a moment."
            onRetry={() => void team.refetch()}
          />
        ) : team.isPending ? (
          <FeedLoading rows={5} />
        ) : (
          <ActivityFeed
            events={team.data}
            emptyTitle="No team activity yet"
            emptyDescription="Activity from your team and AI employees will appear here."
          />
        )}
      </div>
    </WorkspaceContent>
  );
}
