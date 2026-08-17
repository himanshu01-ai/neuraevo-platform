"use client";

import { useState } from "react";
import type { Comment } from "@/services/collaboration";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { formatDayTime } from "@/utils/format";

/**
 * Comments on a notification's subject. Mock only — the composer appends to
 * local state and clears; nothing is sent, and a reload restores the fixture
 * thread. The owner's draft posts as the workspace owner.
 */
export function CommentList({ comments }: { comments: Comment[] }) {
  const [local, setLocal] = useState<Comment[]>([]);
  const [draft, setDraft] = useState("");

  const all = [...comments, ...local];

  const post = () => {
    const body = draft.trim();
    if (!body) return;
    setLocal((rows) => [
      ...rows,
      {
        id: `local_${rows.length + 1}`,
        actor: { id: "user_1", name: "Himanshu", kind: "user", detail: "Workspace owner" },
        body,
        // A deterministic stamp — the mock never reads the clock. Ordered after
        // the fixtures because it's appended.
        createdAt: "2026-07-18T00:00:00Z",
      },
    ]);
    setDraft("");
  };

  return (
    <div className="space-y-3">
      {all.length === 0 ? (
        <p className="text-sm text-muted-foreground">No comments yet. Start the thread below.</p>
      ) : (
        <ul className="space-y-3" aria-label="Comments">
          {all.map((comment) => (
            <li key={comment.id} className="flex gap-2.5">
              <Avatar name={comment.actor.name} className="mt-0.5 size-7 text-[0.625rem]" />
              <div className="min-w-0 flex-1">
                <p className="flex items-baseline gap-2 text-xs">
                  <span className="font-medium text-foreground">{comment.actor.name}</span>
                  <time dateTime={comment.createdAt} className="text-muted-foreground">
                    {formatDayTime(comment.createdAt)}
                  </time>
                </p>
                <p className="mt-0.5 whitespace-pre-wrap break-words text-sm text-muted-foreground">{comment.body}</p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-2 border-t pt-3">
        <label htmlFor="comment-draft" className="sr-only">
          Add a comment
        </label>
        <Textarea
          id="comment-draft"
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a comment…"
        />
        <Button size="sm" onClick={post} disabled={draft.trim().length === 0}>
          Comment
        </Button>
      </div>
    </div>
  );
}
