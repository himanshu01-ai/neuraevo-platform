/**
 * NeuraEvo Design System — Motion Tokens
 *
 * Motion is calm, fast, and purposeful. Durations stay short; easings favor
 * decisive entrances and soft settles. Every consumer must respect
 * `prefers-reduced-motion` (see providers/MotionProvider and
 * docs/03-motion-guidelines.md).
 */

export const duration = {
  instant: 0, //    reduced-motion fallback
  fast: 120, //     hover, press, toggles, micro-interactions
  base: 200, //     default enter/exit, dropdowns, tabs
  slow: 320, //     dialogs, drawers, page section transitions
  slower: 480, //   large surfaces, route transitions
  ambient: 4000, // idle AI Core pulse / breathing loops
} as const;

/** Cubic-bezier easings. Names describe intent, not the curve. */
export const easing = {
  /** Standard ease for most UI. */
  standard: [0.2, 0, 0, 1] as const,
  /** Decisive entrance (elements arriving). */
  entrance: [0.16, 1, 0.3, 1] as const,
  /** Soft exit (elements leaving). */
  exit: [0.4, 0, 1, 1] as const,
  /** Springy emphasis for delight moments (badges, success). */
  emphasized: [0.34, 1.56, 0.64, 1] as const,
  linear: [0, 0, 1, 1] as const,
} as const;

/** Framer Motion spring presets. */
export const spring = {
  /** Snappy UI feedback. */
  snappy: { type: "spring", stiffness: 420, damping: 34, mass: 0.9 },
  /** Smooth panel / drawer motion. */
  smooth: { type: "spring", stiffness: 260, damping: 30 },
  /** Gentle, ambient float. */
  gentle: { type: "spring", stiffness: 120, damping: 20 },
} as const;

/** Canonical named transitions, ready to spread into Framer Motion props. */
export const transition = {
  hover: { duration: duration.fast / 1000, ease: easing.standard },
  enter: { duration: duration.base / 1000, ease: easing.entrance },
  exit: { duration: duration.base / 1000, ease: easing.exit },
  panel: { duration: duration.slow / 1000, ease: easing.entrance },
  route: { duration: duration.slower / 1000, ease: easing.entrance },
} as const;

export type DurationToken = keyof typeof duration;
export type EasingToken = keyof typeof easing;
