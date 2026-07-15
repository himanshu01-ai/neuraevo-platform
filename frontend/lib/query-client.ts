import { QueryClient } from "@tanstack/react-query";

/**
 * TanStack Query client factory. Reserved for future backend calls; in Sprint
 * 17.2 it powers auth mutations that resolve against the mock service adapter.
 */
export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 60_000, retry: 1, refetchOnWindowFocus: false },
      mutations: { retry: 0 },
    },
  });
}
