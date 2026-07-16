"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { employeeKeys, employeesService, type EmployeeDraft } from "@/services/employees";

/**
 * Server-state hooks for employees. Each wraps `services/employees`, so callers
 * never know whether the data came from a mock adapter or a backend.
 *
 * Templates are immutable fixtures, so they get a long `staleTime`; the roster,
 * profiles, and activity are user-owned and refetch more readily.
 */
const LIST_STALE_TIME = 30_000;
const TEMPLATE_STALE_TIME = 600_000;

export function useEmployeeList() {
  return useQuery({
    queryKey: employeeKeys.lists,
    queryFn: employeesService.list,
    staleTime: LIST_STALE_TIME,
  });
}

export function useEmployeeDetail(id: string | null) {
  return useQuery({
    queryKey: employeeKeys.detail(id ?? ""),
    queryFn: () => employeesService.detail(id as string),
    staleTime: LIST_STALE_TIME,
    // The directory renders with nothing selected, so the detail panel asks for
    // an employee that may not exist yet. No id, no request.
    enabled: id !== null,
    retry: false,
  });
}

export function useEmployeeActivity(id: string | null) {
  return useQuery({
    queryKey: employeeKeys.activity(id ?? ""),
    queryFn: () => employeesService.activity(id as string),
    staleTime: LIST_STALE_TIME,
    enabled: id !== null,
    retry: false,
  });
}

export function useEmployeeCapabilities(id: string | null) {
  return useQuery({
    queryKey: employeeKeys.capabilities(id ?? ""),
    queryFn: () => employeesService.capabilities(id as string),
    staleTime: LIST_STALE_TIME,
    enabled: id !== null,
    retry: false,
  });
}

export function useEmployeeTemplates() {
  return useQuery({
    queryKey: employeeKeys.templates,
    queryFn: employeesService.templates,
    staleTime: TEMPLATE_STALE_TIME,
  });
}

export function useEmployeeTemplate(id: string | null) {
  return useQuery({
    queryKey: employeeKeys.template(id ?? ""),
    queryFn: () => employeesService.template(id as string),
    staleTime: TEMPLATE_STALE_TIME,
    enabled: id !== null,
    retry: false,
  });
}

/** Persists a draft through the service seam and refreshes what it invalidates. */
export function useSaveEmployee() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (draft: EmployeeDraft) => employeesService.save(draft),
    onSuccess: (saved) => {
      queryClient.setQueryData(employeeKeys.detail(saved.id), saved);
      void queryClient.invalidateQueries({ queryKey: employeeKeys.lists });
      // A save writes an event and can change which capabilities are held.
      void queryClient.invalidateQueries({ queryKey: employeeKeys.activity(saved.id) });
      void queryClient.invalidateQueries({ queryKey: employeeKeys.capabilities(saved.id) });
    },
  });
}

export function useDuplicateEmployee() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => employeesService.duplicate(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: employeeKeys.lists });
    },
  });
}

export function useArchiveEmployee() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => employeesService.archive(id),
    onSuccess: (archived) => {
      queryClient.setQueryData(employeeKeys.detail(archived.id), archived);
      void queryClient.invalidateQueries({ queryKey: employeeKeys.lists });
      void queryClient.invalidateQueries({ queryKey: employeeKeys.activity(archived.id) });
    },
  });
}

export function useDeleteEmployee() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => employeesService.remove(id),
    onSuccess: (_result, id) => {
      // The employee is gone; its cached profile and history would only serve a
      // stale panel, so they're dropped rather than refetched.
      queryClient.removeQueries({ queryKey: employeeKeys.detail(id) });
      queryClient.removeQueries({ queryKey: employeeKeys.activity(id) });
      queryClient.removeQueries({ queryKey: employeeKeys.capabilities(id) });
      void queryClient.invalidateQueries({ queryKey: employeeKeys.lists });
    },
  });
}
