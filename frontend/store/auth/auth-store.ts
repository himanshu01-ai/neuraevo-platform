import { create } from "zustand";
import type { AuthUser } from "@/services/auth";

/**
 * Client (UI) auth state only — the render-time source of truth. The actual
 * session (JWT pair) lives in the auth service adapter; this store is hydrated
 * from it on bootstrap (see features/auth/hooks/use-auth). Intentionally NOT
 * persisted — token persistence belongs to services/auth/token-storage.
 */
export type AuthStatus = "idle" | "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  status: AuthStatus;
  user: AuthUser | null;
  setUser: (user: AuthUser | null) => void;
  setStatus: (status: AuthStatus) => void;
  reset: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  status: "idle",
  user: null,
  setUser: (user) => set({ user, status: user ? "authenticated" : "unauthenticated" }),
  setStatus: (status) => set({ status }),
  reset: () => set({ user: null, status: "unauthenticated" }),
}));
