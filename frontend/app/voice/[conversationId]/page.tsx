import type { Metadata } from "next";
import { AuthGuard } from "@/features/auth/components/auth-guard";
import { VoiceExperience } from "@/features/voice";

export const metadata: Metadata = { title: "Voice" };

/**
 * The Voice Experience route (Sprint 22). It lives at the app root, *outside*
 * the workspace shell, so the sidebar and chrome fall away for a genuinely
 * immersive full-screen session — a real navigation, not a modal. `AuthGuard`
 * keeps it behind a session; `<Providers>` (React Query, theme) come from the
 * root layout, so the voice mode shares the app's caches and theme.
 */
export default async function VoicePage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = await params;
  return (
    <AuthGuard>
      <VoiceExperience conversationId={conversationId} />
    </AuthGuard>
  );
}
