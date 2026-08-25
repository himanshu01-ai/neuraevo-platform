"use client";

import { useCallback, useEffect } from "react";
import dynamic from "next/dynamic";
import { ArrowLeft, MessagesSquare } from "lucide-react";
import { useConversationStore } from "@/store/conversations";
import { useDrawerDismiss } from "@/hooks/use-drawer-dismiss";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useEmployeeList } from "@/features/employees/hooks/use-employees";
import {
  useConversationDetail,
  useConversationList,
  useConversationMessages,
  useCreateConversation,
  useMarkRead,
  useSendMessage,
  useSetConversationStatus,
  useSetShared,
  useTogglePinned,
} from "../hooks/use-conversations";
import { ConversationList } from "../sidebar/conversation-list";
import { ConversationThread } from "../chat/conversation-thread";
import { Composer } from "../composer/composer";
import { ConversationToolbar } from "./conversation-toolbar";
import {
  ContextPanelLoading,
  ConversationListLoading,
  ThreadLoading,
} from "./conversation-loading";
import { env } from "@/lib/env";
import { cn } from "@/lib/utils";

/**
 * The conversational workspace: toolbar across the top, conversations on the
 * left, the thread in the middle, context on the right, and the composer along
 * the bottom — the primary room where a user and an AI employee meet over
 * work.
 *
 * The context panel is the heavy, optional third of the screen, so it loads on
 * demand. Below `md` the sidebar and the thread trade places on selection —
 * the pattern every chat client trains — and below `xl` the context panel
 * rides over the thread rather than beside it.
 *
 * Nothing on this screen converses. Sending records a message and lands a
 * scripted reply from fixtures; the platform's Conversation Engine is what
 * would answer.
 */

const ContextPanel = dynamic(() => import("./context-panel").then((m) => m.ContextPanel), {
  loading: () => <ContextPanelLoading />,
});

export function ConversationWorkspace({ initialConversationId }: { initialConversationId?: string }) {
  const list = useConversationList();
  const employees = useEmployeeList();
  const selectedId = useConversationStore((s) => s.selectedConversationId);
  const selectConversation = useConversationStore((s) => s.selectConversation);
  const contextPanelOpen = useConversationStore((s) => s.contextPanelOpen);
  const setContextPanelOpen = useConversationStore((s) => s.setContextPanelOpen);

  const detail = useConversationDetail(selectedId);
  const messages = useConversationMessages(selectedId);
  const send = useSendMessage();
  const create = useCreateConversation();
  const togglePinned = useTogglePinned();
  const setShared = useSetShared();
  const setStatus = useSetConversationStatus();
  const markRead = useMarkRead();

  const availableEmployees = (employees.data ?? []).filter((employee) => !employee.isArchived);
  const incompatibleEmployeeSource =
    env.NEXT_PUBLIC_EMPLOYEES_ADAPTER === "mock" &&
    env.NEXT_PUBLIC_CONVERSATIONS_ADAPTER === "backend";
  const isCreateDisabled =
    employees.isPending ||
    employees.isError ||
    incompatibleEmployeeSource ||
    availableEmployees.length === 0;

  // The context panel floats as a drawer below xl: Escape closes it and body
  // scroll locks while it's open, matching the notification inspector.
  const closeContextPanel = useCallback(() => setContextPanelOpen(false), [setContextPanelOpen]);
  useDrawerDismiss(contextPanelOpen && selectedId !== null, closeContextPanel);

  // A deep link (details screen, search hit) lands with its conversation open.
  useEffect(() => {
    if (initialConversationId) selectConversation(initialConversationId);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once per mount by design
  }, [initialConversationId]);

  // A selection outlives the list it came from — a conversation removed
  // elsewhere would leave the thread pointing at nothing.
  useEffect(() => {
    if (!list.data || selectedId === null) return;
    if (!list.data.some((row) => row.id === selectedId)) selectConversation(null);
  }, [list.data, selectedId, selectConversation]);

  // Opening a thread is reading it.
  const markReadMutate = markRead.mutate;
  useEffect(() => {
    if (!selectedId || !list.data) return;
    const row = list.data.find((r) => r.id === selectedId);
    if (row && row.unreadCount > 0) markReadMutate(selectedId);
  }, [selectedId, list.data, markReadMutate]);

  const handleCreate = useCallback(
    (employeeId: string) => {
      create.mutate(
        { title: "New conversation", employeeId },
        { onSuccess: (created) => selectConversation(created.id) }
      );
    },
    [create, selectConversation]
  );

  const isBusy = create.isPending || togglePinned.isPending || setShared.isPending || setStatus.isPending;

  const sidebar = list.isError ? (
    <ErrorState
      compact
      title="Couldn't load conversations"
      description="Try again in a moment."
      onRetry={() => void list.refetch()}
    />
  ) : list.isPending ? (
    <ConversationListLoading />
  ) : (
    <ConversationList conversations={list.data} onSelect={selectConversation} />
  );

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-3 sm:p-4">
      <ConversationToolbar
        conversation={detail.data ?? null}
        employees={availableEmployees}
        onCreate={handleCreate}
        onTogglePinned={() => selectedId && togglePinned.mutate(selectedId)}
        onToggleShared={() =>
          detail.data && setShared.mutate({ id: detail.data.id, shared: !detail.data.shared })
        }
        onToggleArchived={() =>
          detail.data &&
          setStatus.mutate({
            id: detail.data.id,
            status: detail.data.status === "archived" ? "active" : "archived",
          })
        }
        isBusy={isBusy}
        isCreateDisabled={isCreateDisabled}
      />

      {employees.isError ? (
        <Alert variant="error">
          Couldn't load employees. Try again in a moment.
          <Button variant="outline" size="sm" onClick={() => void employees.refetch()} className="ml-3">
            Retry
          </Button>
        </Alert>
      ) : incompatibleEmployeeSource ? (
        <Alert variant="error">
          Offline employee data can't start a server-backed conversation.
        </Alert>
      ) : !employees.isPending && availableEmployees.length === 0 ? (
        <Alert>Create an AI employee before starting a conversation.</Alert>
      ) : null}

      {create.isError ? (
        <Alert variant="error">
          {create.error instanceof Error ? create.error.message : "That conversation couldn't be created."}
        </Alert>
      ) : null}

      <div className="relative flex min-h-0 flex-1 gap-3">
        {/* Conversations */}
        <aside
          aria-label="Conversation list"
          className={cn(
            "w-full min-w-0 flex-col overflow-hidden rounded-lg border bg-card shadow-sm md:flex md:w-80 md:shrink-0",
            selectedId ? "hidden" : "flex"
          )}
        >
          {sidebar}
        </aside>

        {/* Thread + composer */}
        <section
          aria-label="Conversation thread"
          className={cn(
            "min-w-0 flex-1 flex-col overflow-hidden rounded-lg border bg-card shadow-sm md:flex",
            selectedId ? "flex" : "hidden"
          )}
        >
          {selectedId && detail.data ? (
            <>
              <div className="flex items-center gap-2 border-b p-2 md:hidden">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => selectConversation(null)}
                  aria-label="Back to conversations"
                >
                  <ArrowLeft className="size-4" aria-hidden="true" />
                  All conversations
                </Button>
              </div>

              {messages.isPending ? (
                <ThreadLoading className="flex-1" />
              ) : messages.isError ? (
                <ErrorState
                  className="flex-1"
                  title="Couldn't load this thread"
                  description="Its messages couldn't be loaded. Try again in a moment."
                  onRetry={() => void messages.refetch()}
                />
              ) : (
                <ConversationThread
                  conversationId={selectedId}
                  messages={messages.data}
                  employeeName={detail.data.employee.employeeName}
                  isTyping={send.isPending}
                  className="min-h-0 flex-1"
                />
              )}

              <Composer
                conversationId={selectedId}
                employeeName={detail.data.employee.employeeName}
                disabled={detail.data.status === "archived"}
              />
            </>
          ) : selectedId ? (
            <ThreadLoading className="flex-1" />
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <EmptyState
                icon={MessagesSquare}
                title="No conversation selected"
                description="Pick one from the left, or start a new one with an AI employee."
              />
            </div>
          )}
        </section>

        {/* Context panel — beside the thread on xl, over it below */}
        {contextPanelOpen && selectedId ? (
          <>
            <button
              type="button"
              aria-label="Close context panel"
              onClick={() => setContextPanelOpen(false)}
              className="fixed inset-0 z-overlay bg-foreground/20 xl:hidden"
            />
            <aside
              aria-label="Conversation context"
              className={cn(
                "fixed inset-y-0 right-0 z-overlay flex w-80 max-w-[85vw] flex-col overflow-hidden border-l bg-card shadow-lg",
                "xl:static xl:z-auto xl:max-w-none xl:rounded-lg xl:border xl:shadow-sm"
              )}
            >
              {detail.data ? (
                <ContextPanel conversation={detail.data} />
              ) : (
                <ContextPanelLoading />
              )}
            </aside>
          </>
        ) : null}
      </div>
    </div>
  );
}
