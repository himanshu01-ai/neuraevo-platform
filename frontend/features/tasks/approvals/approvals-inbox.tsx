"use client";

import { ApprovalList } from "./approval-list";

/**
 * The reviewer's inbox: every approval across every task, newest first.
 *
 * A named surface rather than `<ApprovalList taskId={null} />` at the route,
 * because "the inbox" is a thing this product has — and the `null` that means
 * "not scoped to a task" is a detail the route shouldn't have to know.
 */
export function TaskApprovalsInbox() {
  return <ApprovalList taskId={null} />;
}
