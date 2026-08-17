"use client";

import Link from "next/link";
import type { Participant } from "@/services/conversations";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

/**
 * Who is in the conversation. The human anchors the list; each AI employee
 * links to its own profile, where the employee module owns the rest.
 */
export function ParticipantList({ participants }: { participants: Participant[] }) {
  return (
    <ul className="flex flex-col gap-2" aria-label="Participants">
      {participants.map((participant) => {
        const isEmployee = participant.role === "assistant";
        const body = (
          <>
            <Avatar name={participant.name} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-foreground">{participant.name}</span>
              <span className="block truncate text-xs text-muted-foreground">{participant.detail}</span>
            </span>
            <Badge variant={isEmployee ? "primary" : "outline"} className="shrink-0">
              {isEmployee ? "AI employee" : "You"}
            </Badge>
          </>
        );

        return (
          <li key={participant.id}>
            {isEmployee ? (
              <Link
                href={`/workspace/employees/${participant.id}`}
                className="flex items-center gap-2.5 rounded-lg border border-transparent p-2 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {body}
              </Link>
            ) : (
              <span className="flex items-center gap-2.5 p-2">{body}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
