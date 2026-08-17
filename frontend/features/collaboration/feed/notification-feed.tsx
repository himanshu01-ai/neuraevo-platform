"use client";

import { motion, useReducedMotion } from "framer-motion";
import { BellOff } from "lucide-react";
import type { NotificationSummary } from "@/services/collaboration";
import { EmptyState } from "@/components/ui/empty-state";
import { NotificationCard } from "./notification-card";
import { cn } from "@/lib/utils";

export interface NotificationFeedProps {
  notifications: NotificationSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onToggle: (
    id: string,
    field: "read" | "archived" | "pinned" | "bookmarked" | "following" | "muted",
    value: boolean
  ) => void;
  compact?: boolean;
  disabled?: boolean;
  /** Shown when the feed is empty after filtering. */
  emptyTitle?: string;
  emptyDescription?: string;
  className?: string;
}

/**
 * The notification feed: a memoized list of cards with a staggered reveal on
 * first paint. Each row animates its opacity/offset in; under
 * prefers-reduced-motion the global MotionConfig drops the transform and the
 * list simply appears.
 */
export function NotificationFeed({
  notifications,
  selectedId,
  onSelect,
  onToggle,
  compact = false,
  disabled = false,
  emptyTitle = "You're all caught up",
  emptyDescription = "New notifications will appear here.",
  className,
}: NotificationFeedProps) {
  const reducedMotion = useReducedMotion();

  if (notifications.length === 0) {
    return <EmptyState icon={BellOff} title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <ul className={cn("flex flex-col gap-2", className)} aria-label="Notifications">
      {notifications.map((notification, index) => (
        <motion.li
          key={notification.id}
          layout={!reducedMotion}
          initial={{ opacity: 0, y: reducedMotion ? 0 : 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: reducedMotion ? 0 : Math.min(index * 0.03, 0.3), ease: [0.16, 1, 0.3, 1] }}
        >
          <NotificationCard
            notification={notification}
            isSelected={selectedId === notification.id}
            onSelect={onSelect}
            onToggle={onToggle}
            compact={compact}
            disabled={disabled}
          />
        </motion.li>
      ))}
    </ul>
  );
}
