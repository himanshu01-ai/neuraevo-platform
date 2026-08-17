"use client";

import { ErrorState } from "@/components/ui/error-state";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { Reveal } from "@/components/motion/reveal";
import { useActivity } from "../hooks/use-collaboration";
import { ActivityFeed } from "../activity/activity-feed";
import { CollaborationHeader } from "./collaboration-header";
import { FeedLoading } from "./collaboration-loading";

/**
 * The personal Activity feed: what you did and were tagged in, newest first.
 * Reuses the shared activity timeline; the team screen is the same feed with a
 * wider audience.
 */
export function ActivityScreen() {
  const activity = useActivity();

  return (
    <WorkspaceContent>
      <Reveal>
        <CollaborationHeader title="Activity" description="What you've done and been tagged in across the workspace." />
      </Reveal>

      <div className="mt-4 max-w-3xl">
        {activity.isError ? (
          <ErrorState
            title="Couldn't load activity"
            description="Your activity couldn't be loaded. Try again in a moment."
            onRetry={() => void activity.refetch()}
          />
        ) : activity.isPending ? (
          <FeedLoading rows={4} />
        ) : (
          <ActivityFeed
            events={activity.data}
            emptyTitle="No activity yet"
            emptyDescription="Actions you take and mentions of you will appear here."
          />
        )}
      </div>
    </WorkspaceContent>
  );
}
