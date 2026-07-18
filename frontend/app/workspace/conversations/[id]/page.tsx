import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { ThreadLoading } from "@/features/conversations";

export const metadata: Metadata = { title: "Conversation" };

const ConversationWorkspace = dynamic(
  () => import("@/features/conversations").then((m) => m.ConversationWorkspace),
  { loading: () => <ThreadLoading /> }
);

/**
 * A conversation's own address — the workspace with that thread open, so a
 * deep link from search, history, or a teammate lands mid-conversation with
 * full context.
 */
export default async function ConversationDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ConversationWorkspace initialConversationId={id} />;
}
