"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { AuthError, authService } from "@/services/auth";
import { useAuthStore } from "@/store/auth";

/** Bootstraps auth state once from the mock session (hydrates the store). */
export function useSessionBootstrap() {
  const status = useAuthStore((s) => s.status);
  const setStatus = useAuthStore((s) => s.setStatus);
  const setUser = useAuthStore((s) => s.setUser);

  useEffect(() => {
    if (status !== "idle") return;
    setStatus("loading");
    authService
      .refreshSession()
      .then((session) => setUser(session?.user ?? null))
      .catch(() => setUser(null));
  }, [status, setStatus, setUser]);
}

/** Human-readable message for any auth error. */
export function authErrorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (error instanceof AuthError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

/** Auth actions as TanStack Query mutations (future backend calls) + logout. */
export function useAuth() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const status = useAuthStore((s) => s.status);
  const setUser = useAuthStore((s) => s.setUser);
  const reset = useAuthStore((s) => s.reset);

  const login = useMutation({
    mutationFn: authService.login,
    onSuccess: (session) => setUser(session.user),
  });

  const signup = useMutation({
    mutationFn: authService.signup,
    onSuccess: (session) => setUser(session.user),
  });

  const forgotPassword = useMutation({ mutationFn: authService.forgotPassword });

  const verifyEmail = useMutation({
    mutationFn: authService.verifyEmail,
    onSuccess: (updated) => setUser(updated),
  });

  const logout = async () => {
    await authService.logout();
    reset();
    router.replace("/login");
  };

  return { user, status, login, signup, forgotPassword, verifyEmail, logout };
}
