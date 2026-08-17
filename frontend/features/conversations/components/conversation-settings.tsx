"use client";

import { useEffect, useState } from "react";
import { Archive, ArchiveRestore, Pin, PinOff, Users } from "lucide-react";
import { useConversationStore } from "@/store/conversations";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/loading-state";
import { Select } from "@/components/ui/select";
import {
  useConversationDetail,
  useConversationList,
  useRenameConversation,
  useSetConversationStatus,
  useSetShared,
  useTogglePinned,
} from "../hooks/use-conversations";

/**
 * Per-conversation settings: title, pin, sharing, and the archive state —
 * every control writing through the same mutations the toolbar uses, so a
 * change made here reads identically everywhere. The conversation under
 * management follows the workspace's selection and can be switched in place.
 */
export function ConversationSettings() {
  const list = useConversationList();
  const selectedId = useConversationStore((s) => s.selectedConversationId);
  const selectConversation = useConversationStore((s) => s.selectConversation);

  // Manage the workspace's selection by default; fall back to the first row.
  const activeId = selectedId ?? list.data?.[0]?.id ?? null;
  const detail = useConversationDetail(activeId);

  const rename = useRenameConversation();
  const togglePinned = useTogglePinned();
  const setShared = useSetShared();
  const setStatus = useSetConversationStatus();

  const [title, setTitle] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  // The form field tracks whichever conversation is being managed.
  useEffect(() => {
    if (detail.data) setTitle(detail.data.title);
  }, [detail.data]);

  if (list.isError) {
    return (
      <ErrorState
        title="Couldn't load conversations"
        description="Settings need the conversation list. Try again in a moment."
        onRetry={() => void list.refetch()}
      />
    );
  }

  if (list.isPending) return <LoadingState rows={4} />;

  if (!activeId || !list.data || list.data.length === 0) {
    return (
      <Alert variant="info">There are no conversations to manage yet. Start one from the workspace.</Alert>
    );
  }

  const conversation = detail.data ?? null;
  const archived = conversation?.status === "archived";
  const isBusy = rename.isPending || togglePinned.isPending || setShared.isPending || setStatus.isPending;

  return (
    <div className="max-w-2xl space-y-6">
      <Field label="Conversation" description="Which conversation these settings manage.">
        {({ id }) => (
          <Select id={id} value={activeId} onChange={(e) => selectConversation(e.target.value)}>
            {list.data.map((row) => (
              <option key={row.id} value={row.id}>
                {row.title} — {row.employee.employeeName}
              </option>
            ))}
          </Select>
        )}
      </Field>

      {notice ? <Alert variant="info">{notice}</Alert> : null}

      {conversation ? (
        <>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setNotice(null);
              rename.mutate(
                { id: conversation.id, title },
                { onSuccess: () => setNotice("Title updated.") }
              );
            }}
            className="space-y-3 rounded-lg border bg-card p-4 shadow-sm"
            aria-label="Rename conversation"
          >
            <Field
              label="Title"
              error={rename.isError ? (rename.error instanceof Error ? rename.error.message : "Couldn't rename.") : undefined}
            >
              {({ id, invalid }) => (
                <Input
                  id={id}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  aria-invalid={invalid}
                  maxLength={255}
                  disabled={isBusy}
                />
              )}
            </Field>
            <Button type="submit" size="sm" disabled={isBusy || title.trim() === conversation.title}>
              Save title
            </Button>
          </form>

          <section aria-label="Conversation preferences" className="space-y-3 rounded-lg border bg-card p-4 shadow-sm">
            <SettingRow
              title={conversation.pinned ? "Pinned to the top" : "Not pinned"}
              description="Pinned conversations lead the sidebar in every ordering."
              action={
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isBusy}
                  onClick={() => {
                    setNotice(null);
                    togglePinned.mutate(conversation.id, {
                      onSuccess: (row) => setNotice(row.pinned ? "Pinned." : "Unpinned."),
                    });
                  }}
                >
                  {conversation.pinned ? <PinOff className="size-4" aria-hidden="true" /> : <Pin className="size-4" aria-hidden="true" />}
                  {conversation.pinned ? "Unpin" : "Pin"}
                </Button>
              }
            />

            <SettingRow
              title={conversation.shared ? "Shared with teammates" : "Private"}
              description="Shared conversations appear on the shared screen for the team."
              action={
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isBusy}
                  onClick={() => {
                    setNotice(null);
                    setShared.mutate(
                      { id: conversation.id, shared: !conversation.shared },
                      { onSuccess: (row) => setNotice(row.shared ? "Now shared." : "No longer shared.") }
                    );
                  }}
                >
                  <Users className="size-4" aria-hidden="true" />
                  {conversation.shared ? "Stop sharing" : "Share"}
                </Button>
              }
            />

            <SettingRow
              title={archived ? "Archived" : "Active"}
              description={
                archived
                  ? "Archived conversations read but don't write. Restore to continue."
                  : "Archiving keeps the record and closes the composer."
              }
              action={
                <Button
                  variant={archived ? "outline" : "destructive"}
                  size="sm"
                  disabled={isBusy}
                  onClick={() => {
                    setNotice(null);
                    setStatus.mutate(
                      { id: conversation.id, status: archived ? "active" : "archived" },
                      { onSuccess: (row) => setNotice(row.status === "archived" ? "Archived." : "Restored.") }
                    );
                  }}
                >
                  {archived ? <ArchiveRestore className="size-4" aria-hidden="true" /> : <Archive className="size-4" aria-hidden="true" />}
                  {archived ? "Restore" : "Archive"}
                </Button>
              }
            />
          </section>
        </>
      ) : (
        <LoadingState rows={3} />
      )}
    </div>
  );
}

function SettingRow({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-3 last:border-b-0 last:pb-0">
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <div className="shrink-0">{action}</div>
    </div>
  );
}
