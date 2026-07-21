"use client";

import { Check, ShieldQuestion, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { type PendingAction } from "../lib/action-intent";

/**
 * The confirmation experience — an inline approval card, never a browser dialog
 * (Sprint 22). When the assistant recognises an outward action it pauses here:
 * the card names the action and paraphrases the request, and the assistant
 * explains aloud why it's asking. Allow proceeds; Cancel backs out gracefully.
 */
export interface VoiceApprovalCardProps {
  action: PendingAction;
  onAllow: () => void;
  onCancel: () => void;
  busy?: boolean;
}

export function VoiceApprovalCard({ action, onAllow, onCancel, busy = false }: VoiceApprovalCardProps) {
  return (
    <section
      role="alertdialog"
      aria-label={`Confirm: ${action.label}`}
      aria-describedby="voice-approval-reason"
      className="w-full max-w-md rounded-2xl border bg-card/95 p-5 shadow-xl backdrop-blur"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-warning/15 text-warning">
          <ShieldQuestion className="size-5" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold text-foreground">{action.label}</h2>
          <p className="mt-1 break-words text-sm text-muted-foreground">“{action.summary}”</p>
          <p id="voice-approval-reason" className="mt-2 text-xs text-muted-foreground">
            {action.reason}
          </p>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-end gap-2">
        <Button variant="ghost" onClick={onCancel} disabled={busy} autoFocus>
          <X className="size-4" aria-hidden="true" />
          Cancel
        </Button>
        <Button onClick={onAllow} disabled={busy}>
          <Check className="size-4" aria-hidden="true" />
          {busy ? "Working…" : "Allow"}
        </Button>
      </div>
    </section>
  );
}
