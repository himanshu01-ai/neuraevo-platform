import type { Metadata } from "next";
import { AuthGuard } from "@/features/auth/components/auth-guard";
import { VoiceLanding } from "@/features/voice";

export const metadata: Metadata = { title: "Voice" };

/**
 * The Voice landing route (Sprint 23). Voice is the platform's headline
 * interaction, so it is a first-class primary-nav destination — not only a
 * button inside a conversation. Like the session route it lives at the app root,
 * outside the workspace shell, so voice reads as its own immersive surface;
 * `AuthGuard` keeps it behind a session and `<Providers>` come from the root
 * layout, so it shares the app's caches and theme.
 */
export default function VoiceLandingPage() {
  return (
    <AuthGuard>
      <VoiceLanding />
    </AuthGuard>
  );
}
