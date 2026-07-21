/**
 * Public surface of the collaboration feature. Routes compose from here and
 * never reach into the feature's internals.
 */
export { NotificationCenter } from "./components/notification-center";
export { NotificationInbox } from "./components/notification-inbox";
export { ActivityScreen } from "./components/activity-screen";
export { TeamActivityScreen } from "./components/team-activity-screen";
export { MentionsScreen } from "./components/mentions-screen";
export { ApprovalsScreen } from "./components/approvals-screen";
export { CollaborationHeader } from "./components/collaboration-header";
export { NotificationInspector } from "./components/notification-inspector";
export { NotificationCard } from "./feed/notification-card";
export { NotificationFeed } from "./feed/notification-feed";
export { QuickActions } from "./feed/quick-actions";
export { ActivityFeed } from "./activity/activity-feed";
export { ApprovalInboxCard } from "./approvals/approval-inbox-card";
export { EntityReferenceCard, EntityChip } from "./references/entity-reference-card";
export { NotificationFilterBar } from "./filters/notification-filters";
export { FeedLoading, InspectorLoading } from "./components/collaboration-loading";
export { COLLABORATION_TABS } from "./models/collaboration-tabs";
export { ResourceCollaborationPanel } from "./components/resource-collaboration-panel";
