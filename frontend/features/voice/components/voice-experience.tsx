"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, MessageSquareText, MicOff, TriangleAlert } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/avatar";
import { useVoiceSession } from "../hooks/use-voice-session";
import { VoiceOrb } from "./voice-orb";
import { VoiceStatus } from "./voice-status";
import { VoiceControls } from "./voice-controls";
import { VoiceApprovalCard } from "./voice-approval-card";
import { VoiceExecution } from "./voice-execution";
import { VoiceHistory } from "./voice-history";
import { cn } from "@/lib/utils";

/**
 * The Voice Experience — a dedicated, immersive full-screen session (Sprint 22).
 *
 * Not a modal or popup: this is a route, so entering Voice Mode is a real
 * navigation the browser and screen readers understand, and the workspace chrome
 * falls away for a calm, focused surface. Everything here is the *experience*
 * layer — the orchestrator hook does the coordinating, reusing the existing
 * conversation turn, memory, AI providers, speech, and Task engine. One
 * intelligent assistant, assembled from parts already built.
 */
export function VoiceExperience({ conversationId }: { conversationId: string }) {
  const router = useRouter();
  const session = useVoiceSession(conversationId);

  const exit = useCallback(() => {
    session.end();
    router.push(`/workspace/conversations/${conversationId}`);
  }, [session, router, conversationId]);

  if (session.isError) {
    return (
      <div className="flex h-dvh flex-col items-center justify-center gap-4 bg-background p-6 text-center">
        <TriangleAlert className="size-10 text-destructive" aria-hidden="true" />
        <div>
          <h1 className="text-lg font-semibold text-foreground">Conversation not found</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            This conversation doesn&apos;t exist, or it was deleted.
          </p>
        </div>
        <Button variant="outline" href="/workspace/conversations">
          <ArrowLeft className="size-4" aria-hidden="true" />
          Back to conversations
        </Button>
      </div>
    );
  }

  const micBlocked = (session.error ?? "").toLowerCase().includes("microphone");

  return (
    <motion.main
      initial={{ opacity: 0, scale: 0.985 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="relative flex h-dvh flex-col overflow-hidden bg-gradient-to-b from-background via-background to-primary/5"
      aria-label={`Voice session with ${session.employeeName}`}
    >
      {/* Header */}
      <header className="flex items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-2.5">
          <Avatar name={session.employeeName} className="size-8 shrink-0 text-xs" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{session.employeeName}</p>
            <p className="text-xs text-muted-foreground">Voice session</p>
          </div>
        </div>
        <Button variant="ghost" onClick={exit} aria-label="Exit voice mode">
          <ArrowLeft className="size-4" aria-hidden="true" />
          <span className="hidden sm:inline">Exit</span>
        </Button>
      </header>

      {/* Fallback / permission guidance */}
      {!session.speechInputSupported ? (
        <div className="px-4 sm:px-6">
          <Alert variant="info" className="mx-auto max-w-2xl">
            <span className="flex items-center gap-2">
              <MicOff className="size-4 shrink-0" aria-hidden="true" />
              Voice input isn&apos;t available in this browser — you can still type below, and
              read the replies.
            </span>
          </Alert>
        </div>
      ) : micBlocked ? (
        <div className="px-4 sm:px-6">
          <Alert variant="warning" className="mx-auto max-w-2xl">
            Microphone access is blocked. Allow it in your browser&apos;s site settings, or type
            below to keep going.
          </Alert>
        </div>
      ) : null}

      {/* Main: orb + status on the left, recent conversation on the right (lg) */}
      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[1fr_20rem]">
        <section className="relative flex min-h-0 flex-col items-center justify-center gap-6 px-4 py-4">
          <VoiceOrb state={session.state} className="size-52 sm:size-64" />

          <VoiceStatus
            state={session.state}
            statusLabel={session.statusLabel}
            transcript={session.transcript}
            micActive={session.micActive}
          />

          {session.execution ? <VoiceExecution execution={session.execution} /> : null}

          {session.error && !micBlocked ? (
            <Alert variant="error" className="max-w-md">
              {session.error}
            </Alert>
          ) : null}

          {/* Approval overlays the centre when the assistant needs a yes/no. */}
          {session.pendingAction ? (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
              className="absolute inset-x-0 bottom-2 flex justify-center px-4"
            >
              <VoiceApprovalCard
                action={session.pendingAction}
                onAllow={session.approve}
                onCancel={session.deny}
                busy={session.execution?.active ?? false}
              />
            </motion.div>
          ) : null}
        </section>

        {/* Recent conversation — beside on lg, a short strip above the controls below */}
        <aside
          aria-label="Conversation history"
          className="hidden min-h-0 flex-col border-l bg-card/40 lg:flex"
        >
          <div className="flex items-center gap-2 border-b px-4 py-3 text-sm font-medium text-muted-foreground">
            <MessageSquareText className="size-4" aria-hidden="true" />
            Conversation
          </div>
          <VoiceHistory
            messages={session.messages}
            employeeName={session.employeeName}
            className="min-h-0 flex-1"
          />
        </aside>
      </div>

      {/* Controls */}
      <footer className="flex justify-center border-t bg-card/60 px-4 py-4 sm:px-6">
        <VoiceControls session={session} />
      </footer>
    </motion.main>
  );
}
