"use client";

import { useMemo } from "react";
import type { ConversationMessage } from "@/services/conversations";
import { isoDay } from "@/utils/format";

/**
 * Shapes a flat thread into what the timeline renders: days, and inside each
 * day, runs of consecutive messages from the same author. A run shares one
 * avatar and one header, so a burst of replies reads as one turn rather than
 * four bubbles with four names.
 *
 * Card messages (approvals, artifacts, references, notifications) break a run:
 * each renders as its own block, so a card never hides inside a text bubble's
 * grouping.
 */

export interface MessageGroup {
  /** `role` of every message in the run. */
  role: ConversationMessage["role"];
  messages: ConversationMessage[];
}

export interface DaySection {
  /** ISO day, e.g. `"2026-07-14"` — the divider formats it for display. */
  day: string;
  groups: MessageGroup[];
}

const breaksRun = (message: ConversationMessage) => message.kind !== "text";

export function useMessageGroups(messages: ConversationMessage[] | undefined): DaySection[] {
  return useMemo(() => {
    if (!messages || messages.length === 0) return [];

    const sections: DaySection[] = [];

    for (const message of messages) {
      const day = isoDay(message.createdAt);
      let section = sections[sections.length - 1];
      if (!section || section.day !== day) {
        section = { day, groups: [] };
        sections.push(section);
      }

      const group = section.groups[section.groups.length - 1];
      const lastMessage = group?.messages[group.messages.length - 1];
      const continuesRun =
        group !== undefined &&
        group.role === message.role &&
        lastMessage !== undefined &&
        !breaksRun(lastMessage) &&
        !breaksRun(message);

      if (continuesRun) {
        group.messages.push(message);
      } else {
        section.groups.push({ role: message.role, messages: [message] });
      }
    }

    return sections;
  }, [messages]);
}
