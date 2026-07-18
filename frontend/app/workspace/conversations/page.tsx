import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { ThreadLoading } from "@/features/conversations";

export const metadata: Metadata = { title: "Conversations" };

const ConversationWorkspace = dynamic(
  () => import("@/features/conversations").then((m) => m.ConversationWorkspace),
  { loading: () => <ThreadLoading /> }
);

export default function ConversationsPage() {
  return <ConversationWorkspace />;
}
