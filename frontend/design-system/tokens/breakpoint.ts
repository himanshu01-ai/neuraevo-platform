/**
 * NeuraEvo Design System — Breakpoint & Grid Tokens
 *
 * Mobile-first. Values align with Tailwind's default screens so utility
 * classes and JS logic never disagree. `2xl` is the max content container;
 * `3xl` unlocks the wide dual-pane workspace layout.
 */

export const breakpoint = {
  sm: "640px", //  large phone / small tablet
  md: "768px", //  tablet — sidebar becomes persistent
  lg: "1024px", // laptop — full app shell
  xl: "1280px", // desktop — default design target
  "2xl": "1536px", // large desktop
  "3xl": "1920px", // ultra-wide — workspace dual-pane + inspector
} as const;

/** Content container max-widths per role. */
export const container = {
  prose: "42rem", //   672px — reading column (docs, single form)
  content: "72rem", // 1152px — standard app content
  wide: "90rem", //    1440px — dashboards, tables
  full: "100%", //     edge-to-edge (workspace canvas, workflow graph)
} as const;

/** The 12-column app grid. */
export const grid = {
  columns: 12,
  gutter: "24px",
  marginDesktop: "32px",
  marginMobile: "16px",
} as const;

export type Breakpoint = keyof typeof breakpoint;
