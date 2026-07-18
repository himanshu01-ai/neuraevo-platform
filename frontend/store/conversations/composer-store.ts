import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Attachment } from "@/services/conversations";

/**
 * The composer's client state. Drafts are keyed by conversation so switching
 * threads never loses what was being typed — and they persist, because a
 * half-written message is the one piece of client state a reload genuinely
 * destroys. Staged attachments are ephemeral: they are mock references, cheap
 * to re-stage and meaningless to restore without their pick context.
 */

/** What the mention menu is completing, or `null` when it's closed. */
export type MentionKind = "employee" | "workflow" | "task" | "memory";

interface ComposerState {
  /** Draft text per conversation id. Absent means empty. */
  drafts: Record<string, string>;
  /** Attachments staged on the next send, per conversation id. */
  staged: Record<string, Attachment[]>;
  /** The open mention menu, if any. */
  activeMention: MentionKind | null;

  setDraft: (conversationId: string, text: string) => void;
  clearDraft: (conversationId: string) => void;
  stageAttachment: (conversationId: string, attachment: Attachment) => void;
  unstageAttachment: (conversationId: string, attachmentId: string) => void;
  clearStaged: (conversationId: string) => void;
  setActiveMention: (kind: MentionKind | null) => void;
}

export const useComposerStore = create<ComposerState>()(
  persist(
    (set) => ({
      drafts: {},
      staged: {},
      activeMention: null,

      setDraft: (conversationId, text) =>
        set((s) => ({ drafts: { ...s.drafts, [conversationId]: text } })),
      clearDraft: (conversationId) =>
        set((s) => {
          const { [conversationId]: _gone, ...rest } = s.drafts;
          return { drafts: rest };
        }),
      stageAttachment: (conversationId, attachment) =>
        set((s) => {
          const current = s.staged[conversationId] ?? [];
          // Staging the same reference twice attaches it once.
          if (current.some((a) => a.id === attachment.id)) return s;
          return { staged: { ...s.staged, [conversationId]: [...current, attachment] } };
        }),
      unstageAttachment: (conversationId, attachmentId) =>
        set((s) => ({
          staged: {
            ...s.staged,
            [conversationId]: (s.staged[conversationId] ?? []).filter((a) => a.id !== attachmentId),
          },
        })),
      clearStaged: (conversationId) =>
        set((s) => {
          const { [conversationId]: _gone, ...rest } = s.staged;
          return { staged: rest };
        }),
      setActiveMention: (activeMention) => set({ activeMention }),
    }),
    { name: "neuraevo.conversations.composer", partialize: (s) => ({ drafts: s.drafts }) }
  )
);
