"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  collaborationKeys,
  collaborationService,
  type ApprovalDecision,
  type NotificationSummary,
} from "@/services/collaboration";

/**
 * Server-state hooks for collaboration. Each wraps `services/collaboration`,
 * so callers never know whether the data came from the mock adapter or a
 * backend.
 *
 * On polling: a notification feed is the canonical live surface, and docs/09
 * says live surfaces poll behind the feature hook. Nothing polls here — the
 * mock raises nothing on its own, so a refetch would return identical bytes.
 * This hook is where Sprint 18 switches polling (or a socket subscription) on,
 * and no component changes when it does.
 */
const FEED_STALE_TIME = 30_000;

export function useNotifications() {
  return useQuery({
    queryKey: collaborationKeys.notifications,
    queryFn: collaborationService.notifications,
    staleTime: FEED_STALE_TIME,
  });
}

export function useNotificationDetail(id: string | null) {
  return useQuery({
    queryKey: collaborationKeys.notification(id ?? ""),
    queryFn: () => collaborationService.notification(id as string),
    staleTime: FEED_STALE_TIME,
    // The center renders with nothing selected. No id, no request.
    enabled: id !== null,
    retry: false,
  });
}

export function useActivity() {
  return useQuery({
    queryKey: collaborationKeys.activity,
    queryFn: collaborationService.activity,
    staleTime: FEED_STALE_TIME,
  });
}

export function useMentions() {
  return useQuery({
    queryKey: collaborationKeys.mentions,
    queryFn: collaborationService.mentions,
    staleTime: FEED_STALE_TIME,
  });
}

export function useTeamActivity() {
  return useQuery({
    queryKey: collaborationKeys.teamActivity,
    queryFn: collaborationService.teamActivity,
    staleTime: FEED_STALE_TIME,
  });
}

export function useApprovals() {
  return useQuery({
    queryKey: collaborationKeys.approvals,
    queryFn: collaborationService.approvals,
    staleTime: FEED_STALE_TIME,
  });
}

export function useCollaborationCounts() {
  return useQuery({
    queryKey: collaborationKeys.counts,
    queryFn: collaborationService.counts,
    staleTime: FEED_STALE_TIME,
  });
}

/** A notification change touches the feed, its own record, and the counts. */
function invalidate(queryClient: ReturnType<typeof useQueryClient>, id?: string) {
  void queryClient.invalidateQueries({ queryKey: collaborationKeys.notifications });
  void queryClient.invalidateQueries({ queryKey: collaborationKeys.counts });
  if (id) void queryClient.invalidateQueries({ queryKey: collaborationKeys.notification(id) });
}

/**
 * One hook for every single-notification toggle. The caller picks the field;
 * the value is optimistic so the row responds before the round-trip, then the
 * server summary settles it.
 */
type ToggleField = "read" | "archived" | "pinned" | "bookmarked" | "following" | "muted";

const SERVICE_BY_FIELD: Record<ToggleField, (id: string, value: boolean) => Promise<NotificationSummary>> = {
  read: collaborationService.markRead,
  archived: collaborationService.setArchived,
  pinned: collaborationService.setPinned,
  bookmarked: collaborationService.setBookmarked,
  following: collaborationService.setFollowing,
  muted: collaborationService.setMuted,
};

export function useNotificationToggle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, field, value }: { id: string; field: ToggleField; value: boolean }) =>
      SERVICE_BY_FIELD[field](id, value),
    onMutate: ({ id, field, value }) => {
      queryClient.setQueryData<NotificationSummary[]>(collaborationKeys.notifications, (rows) =>
        rows?.map((row) => (row.id === id ? { ...row, [field]: value } : row))
      );
    },
    onSuccess: (summary) => invalidate(queryClient, summary.id),
  });
}

export function useMarkAllRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => collaborationService.markAllRead(),
    onSuccess: (rows) => {
      queryClient.setQueryData(collaborationKeys.notifications, rows);
      invalidate(queryClient);
    },
  });
}

/** Records a reviewer's decision on an approval. UI only — nothing runs. */
export function useDecideApproval() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (decision: ApprovalDecision) => collaborationService.decide(decision),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: collaborationKeys.approvals });
      void queryClient.invalidateQueries({ queryKey: collaborationKeys.counts });
    },
  });
}
