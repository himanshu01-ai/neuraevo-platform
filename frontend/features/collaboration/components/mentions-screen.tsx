"use client";

import { ErrorState } from "@/components/ui/error-state";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { Reveal } from "@/components/motion/reveal";
import { useMentions } from "../hooks/use-collaboration";
import { ActivityFeed } from "../activity/activity-feed";
import { CollaborationHeader } from "./collaboration-header";
import { FeedLoading } from "./collaboration-loading";

/**
 * The Mentions feed: everywhere you were @-mentioned, newest first. A focused
 * slice of activity — the adapter filters to the `mentioned` kind so this
 * screen never has to know how a mention is stored.
 */
export function MentionsScreen() {
  const mentions = useMentions();

  return (
    <WorkspaceContent>
      <Reveal>
        <CollaborationHeader title="Mentions" description="Everywhere you've been mentioned across conversations and tasks." />
      </Reveal>

      <div className="mt-4 max-w-3xl">
        {mentions.isError ? (
          <ErrorState
            title="Couldn't load mentions"
            description="Your mentions couldn't be loaded. Try again in a moment."
            onRetry={() => void mentions.refetch()}
          />
        ) : mentions.isPending ? (
          <FeedLoading rows={3} />
        ) : (
          <ActivityFeed
            events={mentions.data}
            emptyTitle="No mentions yet"
            emptyDescription="When someone mentions you, it'll show up here."
          />
        )}
      </div>
    </WorkspaceContent>
  );
}
