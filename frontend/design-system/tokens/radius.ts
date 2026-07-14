/**
 * NeuraEvo Design System — Radius Tokens
 *
 * Soft, calm corners. `md` (0.75rem) is the base `--radius`; shadcn derives
 * sm/lg from it. Fully-rounded (`full`) is reserved for avatars, status dots,
 * and pill badges only.
 */

export const radius = {
  none: "0px",
  xs: "0.25rem", // 4px  — inline chips, tags
  sm: "0.5rem", //  8px  — inputs, small buttons
  md: "0.75rem", // 12px — DEFAULT: buttons, cards, popovers
  lg: "1rem", //    16px — panels, dialogs
  xl: "1.5rem", //  24px — hero cards, feature surfaces
  full: "9999px", //      pills, avatars, status dots
} as const;

export type RadiusToken = keyof typeof radius;
