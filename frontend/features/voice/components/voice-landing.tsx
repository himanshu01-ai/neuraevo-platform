"use client";

import Link from "next/link";
import { AudioLines, MessagesSquare, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { useConversationList } from "@/features/conversations/hooks/use-conversations";

/**
 * The Voice landing (Sprint 23). Voice is a per-conversation, full-screen
 * experience entered from `/voice/{conversationId}`, so before this it had no
 * home of its own — only a button buried in the conversation toolbar. This
 * page is that home: the primary-nav "Voice" destination lists the user's
 * conversations and opens any of them in a spoken session, so voice is reachable
 * without first hunting down a thread. It reuses the conversation list (same
 * React Query cache as the workspace) and adds no second source of truth.
 */
export function VoiceLanding() {
  const conversations = useConversationList();

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-2xl flex-col gap-8 px-6 py-12">
      <header className="space-y-3">
        <Link
          href="/workspace/conversations"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Back to workspace
        </Link>
        <div className="flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-full bg-primary/10 text-primary">
            <AudioLines className="size-6" aria-hidden="true" />
          </span>
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Voice</h1>
            <p className="text-sm text-muted-foreground">
              Pick a conversation to talk to — hands-free, out loud.
            </p>
          </div>
        </div>
      </header>

      {conversations.isPending ? (
        <LoadingState label="Loading your conversations" rows={4} />
      ) : conversations.isError ? (
        <ErrorState
          title="Your conversations couldn't be loaded"
          description="Please try again."
          onRetry={() => void conversations.refetch()}
        />
      ) : conversations.data.length === 0 ? (
        <EmptyState
          icon={MessagesSquare}
          title="No conversations yet"
          description="Start a conversation with an AI employee, then come back to talk to it."
          action={
            <Button href="/workspace/conversations">Go to conversations</Button>
          }
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {conversations.data.map((conversation) => (
            <li key={conversation.id}>
              <Link
                href={`/voice/${conversation.id}`}
                aria-label={`Start a voice session with ${conversation.employee.employeeName}`}
                className="group flex items-center gap-4 rounded-xl border border-border bg-card px-4 py-3.5 transition-colors hover:border-primary/50 hover:bg-accent"
              >
                <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary transition-transform group-hover:scale-105">
                  <AudioLines className="size-5" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-foreground">
                    {conversation.title}
                  </span>
                  <span className="block truncate text-sm text-muted-foreground">
                    {conversation.employee.employeeName}
                    {conversation.lastMessagePreview
                      ? ` · ${conversation.lastMessagePreview}`
                      : ""}
                  </span>
                </span>
                <span className="hidden shrink-0 text-sm font-medium text-primary sm:inline">
                  Talk
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
