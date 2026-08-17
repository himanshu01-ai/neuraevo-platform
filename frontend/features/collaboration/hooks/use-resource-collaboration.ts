"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  resourceCollaborationKeys,
  resourceCollaborationService,
  type AddParticipantInput,
  type CollaborationResourceType,
  type CollaborationRole,
  type CreateShareInput,
} from "@/services/collaboration/resource";

/**
 * Server-state hooks for the resource-collaboration surface (participants,
 * share links, activity). Each wraps `services/collaboration/resource`, so
 * components never know the transport. Reads are permission-aware server-side;
 * a non-participant's queries fail and the panel renders an honest empty/error
 * state.
 */

const STALE_TIME = 15_000;

export function useResourceAccess(
  rt: CollaborationResourceType,
  rid: string
) {
  return useQuery({
    queryKey: resourceCollaborationKeys.access(rt, rid),
    queryFn: () => resourceCollaborationService.access(rt, rid),
    staleTime: STALE_TIME,
    retry: false,
  });
}

export function useParticipants(
  rt: CollaborationResourceType,
  rid: string
) {
  return useQuery({
    queryKey: resourceCollaborationKeys.participants(rt, rid),
    queryFn: () => resourceCollaborationService.participants(rt, rid),
    staleTime: STALE_TIME,
    retry: false,
  });
}

export function useResourceActivity(
  rt: CollaborationResourceType,
  rid: string
) {
  return useQuery({
    queryKey: resourceCollaborationKeys.activity(rt, rid),
    queryFn: () => resourceCollaborationService.activity(rt, rid),
    staleTime: STALE_TIME,
    retry: false,
  });
}

/** Share links are owner-only; gate the query on `enabled` so viewers don't 403. */
export function useShares(
  rt: CollaborationResourceType,
  rid: string,
  enabled: boolean
) {
  return useQuery({
    queryKey: resourceCollaborationKeys.shares(rt, rid),
    queryFn: () => resourceCollaborationService.shares(rt, rid),
    staleTime: STALE_TIME,
    enabled,
    retry: false,
  });
}

/** A participant change touches the roster, the activity feed, and my access. */
function invalidateResource(
  queryClient: ReturnType<typeof useQueryClient>,
  rt: CollaborationResourceType,
  rid: string
) {
  void queryClient.invalidateQueries({
    queryKey: resourceCollaborationKeys.participants(rt, rid),
  });
  void queryClient.invalidateQueries({
    queryKey: resourceCollaborationKeys.activity(rt, rid),
  });
}

export function useAddParticipant(
  rt: CollaborationResourceType,
  rid: string
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AddParticipantInput) =>
      resourceCollaborationService.addParticipant(rt, rid, input),
    onSuccess: () => invalidateResource(queryClient, rt, rid),
  });
}

export function useUpdateParticipantRole(
  rt: CollaborationResourceType,
  rid: string
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (vars: { participantId: string; role: CollaborationRole }) =>
      resourceCollaborationService.updateRole(rt, rid, vars.participantId, vars.role),
    onSuccess: () => invalidateResource(queryClient, rt, rid),
  });
}

export function useRemoveParticipant(
  rt: CollaborationResourceType,
  rid: string
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (participantId: string) =>
      resourceCollaborationService.removeParticipant(rt, rid, participantId),
    onSuccess: () => invalidateResource(queryClient, rt, rid),
  });
}

export function useCreateShare(
  rt: CollaborationResourceType,
  rid: string
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateShareInput) =>
      resourceCollaborationService.createShare(rt, rid, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: resourceCollaborationKeys.shares(rt, rid),
      });
      invalidateResource(queryClient, rt, rid);
    },
  });
}

export function useRevokeShare(
  rt: CollaborationResourceType,
  rid: string
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (shareId: string) =>
      resourceCollaborationService.revokeShare(rt, rid, shareId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: resourceCollaborationKeys.shares(rt, rid),
      });
      invalidateResource(queryClient, rt, rid);
    },
  });
}
