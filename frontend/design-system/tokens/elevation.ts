/**
 * NeuraEvo Design System — Elevation Tokens
 *
 * Restrained, low-spread shadows. Enterprise surfaces read as flat planes
 * separated by hairline borders first, shadow second. In dark mode elevation
 * is expressed primarily through surface lightness, not shadow.
 */

export const shadow = {
  none: "none",
  /** Hairline lift — hoverable rows, subtle cards. */
  xs: "0 1px 2px 0 rgb(16 17 22 / 0.04)",
  /** Resting card. */
  sm: "0 1px 3px 0 rgb(16 17 22 / 0.06), 0 1px 2px -1px rgb(16 17 22 / 0.06)",
  /** Raised card / dropdown. */
  md: "0 4px 12px -2px rgb(16 17 22 / 0.08), 0 2px 6px -2px rgb(16 17 22 / 0.06)",
  /** Popover / command palette. */
  lg: "0 12px 28px -6px rgb(16 17 22 / 0.12), 0 4px 10px -4px rgb(16 17 22 / 0.08)",
  /** Modal / dialog. */
  xl: "0 24px 56px -12px rgb(16 17 22 / 0.22), 0 8px 20px -8px rgb(16 17 22 / 0.12)",
  /** Focus/brand glow — accent surfaces, AI Core. */
  glow: "0 0 0 1px rgb(108 92 242 / 0.30), 0 8px 32px -8px rgb(108 92 242 / 0.35)",
} as const;

/** Opacity steps for scrims, overlays, disabled states, and glass surfaces. */
export const opacity = {
  0: "0",
  disabled: "0.4",
  muted: "0.6",
  scrim: "0.6",
  hover: "0.08",
  press: "0.12",
  full: "1",
} as const;

export type ShadowToken = keyof typeof shadow;
