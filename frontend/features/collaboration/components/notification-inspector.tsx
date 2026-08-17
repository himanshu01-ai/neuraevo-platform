"use client";

import type { NotificationDetail } from "@/services/collaboration";
import {
  ACTIVITY_KIND_LABEL,
  ACTIVITY_KIND_TONE,
  NOTIFICATION_TYPE_LABEL,
  NOTIFICATION_TYPE_TONE,
} from "@/services/collaboration";
import { PRIORITY_LABEL, PRIORITY_TONE } from "@/types/domain";
import { useCollaborationStore, type InspectorTab } from "@/store/collaboration";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { TONE_DOT, TONE_VARIANT } from "@/components/ui/status-badge";
import { formatDateTime } from "@/utils/format";
import { NOTIFICATION_TYPE_ICON, TONE_SURFACE } from "../models/notification-meta";
import { EntityReferenceCard } from "../references/entity-reference-card";
import { CommentList } from "./comment-list";
import { cn } from "@/lib/utils";

const TABS: { id: InspectorTab; label: string }[] = [
  { id: "details", label: "Details" },
  { id: "related", label: "Related" },
  { id: "history", label: "History" },
];

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{children}</h3>;
}

/**
 * The inspector for a selected notification: its metadata, every record it
 * touches (each through the shared reference card), and its history — plus the
 * collaboration layer, watchers and comments. Tabbed so a long detail doesn't
 * push the feed off-screen; the active tab lives in the store so it survives a
 * reselection.
 */
export function NotificationInspector({ notification }: { notification: NotificationDetail }) {
  const tab = useCollaborationStore((s) => s.inspectorTab);
  const setTab = useCollaborationStore((s) => s.setInspectorTab);

  const Icon = NOTIFICATION_TYPE_ICON[notification.type];
  const tone = NOTIFICATION_TYPE_TONE[notification.type];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-start gap-3 border-b p-4">
        <span
          className={cn("inline-flex size-9 shrink-0 items-center justify-center rounded-md", TONE_SURFACE[tone])}
          aria-hidden="true"
        >
          <Icon className="size-4" />
        </span>
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-foreground">{notification.title}</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {NOTIFICATION_TYPE_LABEL[notification.type]} · from {notification.source.name}
          </p>
        </div>
      </div>

      <div role="tablist" aria-label="Notification detail" className="flex gap-1 border-b p-2">
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
        {tab === "details" ? (
          <>
            <section className="space-y-2">
              <SectionHeading>Metadata</SectionHeading>
              <dl className="space-y-1.5 text-sm">
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Type</dt>
                  <dd className="inline-flex items-center gap-1.5 text-foreground">
                    <span aria-hidden="true" className={cn("size-1.5 rounded-full", TONE_DOT[tone])} />
                    {NOTIFICATION_TYPE_LABEL[notification.type]}
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Priority</dt>
                  <dd>
                    <Badge variant={TONE_VARIANT[PRIORITY_TONE[notification.priority]]}>
                      {PRIORITY_LABEL[notification.priority]}
                    </Badge>
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Status</dt>
                  <dd className="text-foreground">{notification.read ? "Read" : "Unread"}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Received</dt>
                  <dd className="text-right text-foreground">{formatDateTime(notification.createdAt)}</dd>
                </div>
              </dl>
              <p className="pt-1 text-sm text-muted-foreground">{notification.description}</p>
            </section>

            {notification.watchers.length > 0 ? (
              <section className="space-y-2">
                <SectionHeading>Watchers</SectionHeading>
                <ul className="flex flex-col gap-2" aria-label="Watchers">
                  {notification.watchers.map((watcher) => (
                    <li key={watcher.id} className="flex items-center gap-2.5">
                      <Avatar name={watcher.name} className="size-7 text-[0.625rem]" />
                      <span className="min-w-0">
                        <span className="block truncate text-sm text-foreground">{watcher.name}</span>
                        <span className="block truncate text-xs text-muted-foreground">{watcher.detail}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            <section className="space-y-2">
              <SectionHeading>Comments</SectionHeading>
              <CommentList comments={notification.comments} />
            </section>
          </>
        ) : null}

        {tab === "related" ? (
          <section className="space-y-2">
            <SectionHeading>Related records</SectionHeading>
            {notification.relatedEntities.length === 0 ? (
              <p className="text-sm text-muted-foreground">This notification isn&apos;t tied to a specific record.</p>
            ) : (
              <div className="space-y-2">
                {notification.relatedEntities.map((entity, index) => (
                  <EntityReferenceCard key={`${entity.kind}_${index}`} entity={entity} />
                ))}
              </div>
            )}
          </section>
        ) : null}

        {tab === "history" ? (
          <section className="space-y-2">
            <SectionHeading>History</SectionHeading>
            <ol className="space-y-3" aria-label="History">
              {notification.history.map((entry) => (
                <li key={entry.id} className="flex gap-2.5">
                  <span
                    aria-hidden="true"
                    className={cn("mt-1.5 size-2 shrink-0 rounded-full", TONE_DOT[ACTIVITY_KIND_TONE[entry.kind]])}
                  />
                  <div className="min-w-0">
                    <p className="text-sm text-foreground">{entry.summary}</p>
                    <p className="text-xs text-muted-foreground">
                      {ACTIVITY_KIND_LABEL[entry.kind]} · {entry.actor.name} · {formatDateTime(entry.createdAt)}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        ) : null}
      </div>
    </div>
  );
}
