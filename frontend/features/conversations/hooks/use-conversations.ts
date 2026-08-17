"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  conversationKeys,
  conversationService,
  type ConversationApprovalDecision,
  type ConversationDraft,
  type ConversationMessage,
  type ConversationSearchQuery,
  type ConversationStatus,
  type ConversationSummary,
  type OutgoingMessage,
} from "@/services/conversations";
import { useConversationStore } from "@/store/conversations";

/**
 * Server-state hooks for conversations. Each wraps `services/conversations`,
 * so callers never know whether the data came from the mock adapter or the
 * Sprint 5 backend.
 *
 * On polling: a live thread is where docs/09 says polling would go, and
 * nothing polls here — the mock advances nothing on its own, so a refetch
 * would return identical bytes. This hook is where Sprint 18 switches it on,
 * and no component changes when it does.
 */
const LIST_STALE_TIME = 30_000;

export function useConversationList() {
  return useQuery({
    queryKey: conversationKeys.lists,
    queryFn: conversationService.list,
    staleTime: LIST_STALE_TIME,
  });
}

export function useConversationDetail(id: string | null) {
  return useQuery({
    queryKey: conversationKeys.detail(id ?? ""),
    queryFn: () => conversationService.detail(id as string),
    staleTime: LIST_STALE_TIME,
    // The workspace renders with nothing selected. No id, no request.
    enabled: id !== null,
    retry: false,
  });
}

export function useConversationMessages(id: string | null) {
  return useQuery({
    queryKey: conversationKeys.messages(id ?? ""),
    queryFn: () => conversationService.messages(id as string),
    staleTime: LIST_STALE_TIME,
    enabled: id !== null,
    retry: false,
  });
}

export function useConversationSuggestions(id: string | null) {
  return useQuery({
    queryKey: conversationKeys.suggestions(id),
    queryFn: () => conversationService.suggestions(id),
    staleTime: LIST_STALE_TIME,
  });
}

/** Runs only when asked — the search screen submits, it doesn't type-ahead the adapter. */
export function useConversationSearch(query: ConversationSearchQuery, enabled: boolean) {
  return useQuery({
    queryKey: conversationKeys.search(query),
    queryFn: () => conversationService.search(query),
    staleTime: LIST_STALE_TIME,
    enabled,
    retry: false,
  });
}

/** A summary change touches the list and the conversation's own record. */
function invalidateConversation(queryClient: ReturnType<typeof useQueryClient>, id: string) {
  void queryClient.invalidateQueries({ queryKey: conversationKeys.lists });
  void queryClient.invalidateQueries({ queryKey: conversationKeys.detail(id) });
}

export function useCreateConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (draft: ConversationDraft) => conversationService.create(draft),
    onSuccess: (created) => {
      queryClient.setQueryData(conversationKeys.detail(created.id), created);
      queryClient.setQueryData(conversationKeys.messages(created.id), []);
      void queryClient.invalidateQueries({ queryKey: conversationKeys.lists });
    },
  });
}

export function useRenameConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => conversationService.rename(id, title),
    onSuccess: (detail) => {
      queryClient.setQueryData(conversationKeys.detail(detail.id), detail);
      invalidateConversation(queryClient, detail.id);
    },
  });
}

export function useSetConversationStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: ConversationStatus }) =>
      conversationService.setStatus(id, status),
    onSuccess: (detail) => {
      queryClient.setQueryData(conversationKeys.detail(detail.id), detail);
      invalidateConversation(queryClient, detail.id);
    },
  });
}

export function useTogglePinned() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => conversationService.togglePinned(id),
    onSuccess: (summary) => invalidateConversation(queryClient, summary.id),
  });
}

export function useSetShared() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, shared }: { id: string; shared: boolean }) =>
      conversationService.setShared(id, shared),
    onSuccess: (summary) => invalidateConversation(queryClient, summary.id),
  });
}

/**
 * Marks a thread caught up the moment it's opened. Fires only when there is
 * something to clear, and settles the list optimistically so the unread badge
 * doesn't linger for a round-trip.
 */
export function useMarkRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => conversationService.markRead(id),
    onMutate: (id) => {
      queryClient.setQueryData<ConversationSummary[]>(conversationKeys.lists, (rows) =>
        rows?.map((row) => (row.id === id ? { ...row, unreadCount: 0 } : row))
      );
    },
    onSuccess: (summary) => invalidateConversation(queryClient, summary.id),
  });
}

/**
 * Sends a message and lands the scripted reply. The user's message is placed
 * into the thread cache immediately (`onMutate`) so the thread shows it while
 * the typing indicator runs; the receipt then lands both messages verbatim and
 * flags the reply for its one streaming reveal.
 */
export function useSendMessage() {
  const queryClient = useQueryClient();
  const setStreamingMessageId = useConversationStore((s) => s.setStreamingMessageId);

  return useMutation({
    mutationFn: ({ id, outgoing }: { id: string; outgoing: OutgoingMessage }) =>
      conversationService.send(id, outgoing),
    onSuccess: (receipt, { id }) => {
      queryClient.setQueryData<ConversationMessage[]>(conversationKeys.messages(id), (thread) => {
        const rest = (thread ?? []).filter(
          (m) => m.id !== receipt.userMessage.id && m.id !== receipt.assistantMessage.id
        );
        return [...rest, receipt.userMessage, receipt.assistantMessage];
      });
      setStreamingMessageId(receipt.assistantMessage.id);
      invalidateConversation(queryClient, id);
    },
  });
}

/** Records a reviewer's decision on an in-thread approval card. UI only. */
export function useDecideConversationApproval() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (decision: ConversationApprovalDecision) => conversationService.decide(decision),
    onSuccess: (message) => {
      queryClient.setQueryData<ConversationMessage[]>(
        conversationKeys.messages(message.conversationId),
        (thread) => thread?.map((m) => (m.id === message.id ? message : m))
      );
    },
  });
}
