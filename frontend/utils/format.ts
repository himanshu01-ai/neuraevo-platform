/**
 * Pure formatting helpers — dates and byte sizes.
 *
 * The `utils/` README anticipates this module; it stays dependency-free and has
 * no React, no design tokens, and no I/O.
 *
 * ## Why the formatters are pinned
 *
 * These render during SSR *and* during hydration. `toLocaleDateString()` with no
 * arguments resolves against the host's locale and time zone, which differ
 * between the Node process and the browser — so the server would emit
 * "01/07/2026", the client "7/1/2026", and React would report a hydration
 * mismatch on a date nobody chose to format ambiguously.
 *
 * Pinning the locale and the time zone makes the output a function of its input
 * and nothing else. UTC is the right zone because the backend stores
 * `created_at` as `DateTime(timezone=True)` and serialises in UTC: showing the
 * viewer's local day would silently disagree with the day the API reports.
 */

/** Fixed formatters — constructed once, identical on the server and the client. */
const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  timeZone: "UTC",
  day: "numeric",
  month: "short",
  year: "numeric",
});

const DATE_TIME_FORMAT = new Intl.DateTimeFormat("en-GB", {
  timeZone: "UTC",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** `"2026-07-01T09:30:00Z"` → `"1 Jul 2026"`. Invalid input returns an em dash. */
export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return DATE_FORMAT.format(date);
}

/** `"2026-07-01T09:30:00Z"` → `"1 Jul 2026, 09:30"`. Invalid input returns an em dash. */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return `${DATE_TIME_FORMAT.format(date)} UTC`;
}

const TIME_FORMAT = new Intl.DateTimeFormat("en-GB", {
  timeZone: "UTC",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** `"2026-07-01T09:30:00Z"` → `"09:30"`. Invalid input returns an em dash. */
export function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return TIME_FORMAT.format(date);
}

const DAY_TIME_FORMAT = new Intl.DateTimeFormat("en-GB", {
  timeZone: "UTC",
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/**
 * `"2026-07-01T09:30:00Z"` → `"1 Jul, 09:30"`. A compact day+time for dense
 * feeds. Pinned like the others — no clock read, so no hydration mismatch (a
 * live "2 hours ago" can't be made deterministic across server and client, so
 * this app shows the moment, not the distance from now). Invalid input returns
 * an em dash.
 */
export function formatDayTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return DAY_TIME_FORMAT.format(date);
}

/** Sortable ordinal for an ISO string; `0` when it can't be read. */
export function dateValue(iso: string): number {
  const value = new Date(iso).getTime();
  return Number.isNaN(value) ? 0 : value;
}

/** ISO date part (`"2026-07-01"`), for comparing days without a time zone. */
export function isoDay(iso: string): string {
  return iso.slice(0, 10);
}

const UNITS = ["B", "KB", "MB", "GB"] as const;

/**
 * `1536` → `"1.5 KB"`. Uses 1024-steps and at most one decimal, dropping a
 * trailing `.0` so whole values read as whole.
 */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${Math.round(bytes)} B`;

  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }

  const rounded = Math.round(value * 10) / 10;
  const text = Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
  return `${text} ${UNITS[unit]}`;
}

/** `0.42` → `"42%"`. Clamped to 0–100; input is a 0–1 ratio. */
export function formatPercent(ratio: number): string {
  if (!Number.isFinite(ratio)) return "—";
  return `${Math.round(Math.min(1, Math.max(0, ratio)) * 100)}%`;
}
