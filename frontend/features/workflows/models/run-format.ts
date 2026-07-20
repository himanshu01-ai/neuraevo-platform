/**
 * How a run reads (Sprint 18.10).
 *
 * One module so the history list, the detail panel and the summary line all
 * word a duration and a moment the same way. Nothing here fetches, decides or
 * formats anything the platform should have said itself — it turns numbers the
 * platform recorded into the words a person reads.
 */

/**
 * A duration, at the precision that is actually meaningful.
 *
 * Sub-second runs are the common case for a Python step, and "0s" would read as
 * "nothing happened" rather than "very fast" — so milliseconds are kept until
 * seconds are worth having.
 */
export function formatDuration(durationMs: number | null): string {
  if (durationMs === null || Number.isNaN(durationMs)) return "—";
  if (durationMs < 1000) return `${Math.max(0, Math.round(durationMs))}ms`;

  const seconds = durationMs / 1000;
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`;

  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  return remainder === 0 ? `${minutes}m` : `${minutes}m ${remainder}s`;
}

/**
 * When something happened, relative to now, in words.
 *
 * Relative because history is read as "the last one, the one before that" far
 * more often than as a calendar. The exact instant stays available as the
 * element's `title`, so nothing is lost by the shorter reading.
 */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "—";

  const seconds = Math.round((now.getTime() - at.getTime()) / 1000);
  if (seconds < 0) return "just now";
  if (seconds < 45) return "just now";

  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;

  return at.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** The full instant, for the tooltip behind a relative time. */
export function formatExactTime(iso: string): string {
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? "" : at.toLocaleString();
}
