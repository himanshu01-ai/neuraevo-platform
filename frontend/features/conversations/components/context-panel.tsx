"use client";

import Link from "next/link";
import { Pin } from "lucide-react";
import type { ConversationDetail } from "@/services/conversations";
import { CONVERSATION_STATUS_LABEL, CONVERSATION_STATUS_TONE } from "@/services/conversations";
import { useConversationStore, type ContextPanelTab } from "@/store/conversations";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { TONE_VARIANT } from "@/components/ui/status-badge";
import { formatDateTime } from "@/utils/format";
import { ATTACHMENT_KIND_META } from "../models/message-kinds";
import { ReferenceCard } from "../references/reference-card";
import { ParticipantList } from "../participants/participant-list";
import { cn } from "@/lib/utils";

const TABS: { id: ContextPanelTab; label: string }[] = [
  { id: "context", label: "Context" },
  { id: "participants", label: "People" },
  { id: "pinned", label: "Pinned" },
];

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{children}</h3>
  );
}

/**
 * The right-hand panel: what this conversation is about. Context shows the
 * active employee, every referenced workflow, task and memory, the metadata
 * and the tags; People shows participants; Pinned shows what's been kept on
 * top. Reference rows reuse the same card the thread renders, so a workflow
 * looks the same wherever it appears.
 */
export function ContextPanel({ conversation, className }: { conversation: ConversationDetail; className?: string }) {
  const tab = useConversationStore((s) => s.contextPanelTab);
  const setTab = useConversationStore((s) => s.setContextPanelTab);

  return (
    <div className={cn("flex h-full min-h-0 flex-col", className)}>
      <div role="tablist" aria-label="Conversation context" className="flex gap-1 border-b p-2">
        {TABS.map((entry) => (
          <button
            key={entry.id}
            role="tab"
            type="button"
            aria-selected={tab === entry.id}
            onClick={() => setTab(entry.id)}
            className={cn(
              "flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              tab === entry.id ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent"
            )}
          >
            {entry.label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-4">
        {tab === "context" ? (
          <>
            <section className="space-y-2">
              <SectionHeading>Active AI employee</SectionHeading>
              <Link
                href={`/workspace/employees/${conversation.employee.employeeId}`}
                className="flex items-center gap-2.5 rounded-lg border bg-card p-3 shadow-sm transition-all hover:border-primary/30 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Avatar name={conversation.employee.employeeName} />
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-foreground">
                    {conversation.employee.employeeName}
                  </span>
                  <span className="block text-xs text-muted-foreground">{conversation.employee.roleTitle}</span>
                </span>
              </Link>
            </section>

            {conversation.referencedWorkflows.length > 0 ? (
              <section className="space-y-2">
                <SectionHeading>Referenced workflows</SectionHeading>
                {conversation.referencedWorkflows.map((workflow) => (
                  <ReferenceCard key={workflow.workflowId} payload={{ kind: "workflow", workflow }} />
                ))}
              </section>
            ) : null}

            {conversation.referencedTasks.length > 0 ? (
              <section className="space-y-2">
                <SectionHeading>Referenced tasks</SectionHeading>
                {conversation.referencedTasks.map((task) => (
                  <ReferenceCard key={task.taskId} payload={{ kind: "task", task }} />
                ))}
              </section>
            ) : null}

            {conversation.referencedMemories.length > 0 ? (
              <section className="space-y-2">
                <SectionHeading>Referenced memories</SectionHeading>
                {conversation.referencedMemories.map((memory) => (
                  <ReferenceCard key={memory.memoryId} payload={{ kind: "memory", memory }} />
                ))}
              </section>
            ) : null}

            <section className="space-y-2">
              <SectionHeading>About this conversation</SectionHeading>
              <dl className="space-y-1.5 text-sm">
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Status</dt>
                  <dd>
                    <Badge variant={TONE_VARIANT[CONVERSATION_STATUS_TONE[conversation.status]]}>
                      {CONVERSATION_STATUS_LABEL[conversation.status]}
                    </Badge>
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Messages</dt>
                  <dd className="text-foreground">{conversation.messageCount}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Started</dt>
                  <dd className="text-right text-foreground">{formatDateTime(conversation.createdAt)}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Last activity</dt>
                  <dd className="text-right text-foreground">{formatDateTime(conversation.updatedAt)}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Sharing</dt>
                  <dd className="text-foreground">{conversation.shared ? "Shared with teammates" : "Private"}</dd>
                </div>
              </dl>
            </section>

            {conversation.tags.length > 0 ? (
              <section className="space-y-2">
                <SectionHeading>Tags</SectionHeading>
                <ul className="flex flex-wrap gap-1.5" aria-label="Tags">
                  {conversation.tags.map((tag) => (
                    <li key={tag}>
                      <Badge variant="outline">{tag}</Badge>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </>
        ) : null}

        {tab === "participants" ? (
          <section className="space-y-2">
            <SectionHeading>Participants</SectionHeading>
            <ParticipantList participants={conversation.participants} />
          </section>
        ) : null}

        {tab === "pinned" ? (
          <section className="space-y-2">
            <SectionHeading>Pinned items</SectionHeading>
            {conversation.pinnedItems.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nothing pinned in this conversation yet.</p>
            ) : (
              <ul className="flex flex-col gap-1.5" aria-label="Pinned items">
                {conversation.pinnedItems.map((item) => {
                  const Icon = ATTACHMENT_KIND_META[item.kind].icon;
                  const body = (
                    <>
                      <Pin className="size-3 shrink-0 text-primary" aria-hidden="true" />
                      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      <span className="truncate text-sm text-foreground">{item.label}</span>
                    </>
                  );
                  return (
                    <li key={item.id}>
                      {item.href ? (
                        <Link
                          href={item.href}
                          className="flex items-center gap-2 rounded-md border bg-card p-2.5 shadow-sm transition-colors hover:border-primary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          {body}
                        </Link>
                      ) : (
                        <span className="flex items-center gap-2 rounded-md border bg-card p-2.5 shadow-sm">
                          {body}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        ) : null}
      </div>
    </div>
  );
}
