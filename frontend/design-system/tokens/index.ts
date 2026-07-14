/**
 * NeuraEvo Design System — Token Barrel
 *
 * The single import surface for design tokens:
 *
 *   import { tokens } from "@/design-system/tokens";
 *   tokens.color.brand[500];
 *   tokens.motion.transition.enter;
 *
 * Tokens are the DESIGN reference. Runtime theming is CSS-variable driven
 * (styles/globals.css) and consumed through Tailwind utilities. Reach for the
 * raw tokens only where CSS variables cannot go: Framer Motion, Canvas,
 * React Three Fiber materials, and generated charts.
 */

import { neutral, brand, semantic, themeVars } from "./color";
import { fontFamily, fontSize, fontWeight, lineHeight, letterSpacing, textStyle } from "./typography";
import { space, spacingRole } from "./spacing";
import { radius } from "./radius";
import { shadow, opacity } from "./elevation";
import { borderWidth, borderStyle } from "./border";
import { breakpoint, container, grid } from "./breakpoint";
import { zIndex } from "./zIndex";
import { duration, easing, spring, transition } from "./motion";

export const tokens = {
  color: { neutral, brand, semantic, themeVars },
  type: { fontFamily, fontSize, fontWeight, lineHeight, letterSpacing, textStyle },
  space,
  spacingRole,
  radius,
  shadow,
  opacity,
  border: { width: borderWidth, style: borderStyle },
  breakpoint,
  container,
  grid,
  zIndex,
  motion: { duration, easing, spring, transition },
} as const;

export * from "./color";
export * from "./typography";
export * from "./spacing";
export * from "./radius";
export * from "./elevation";
export * from "./border";
export * from "./breakpoint";
export * from "./zIndex";
export * from "./motion";

export type Tokens = typeof tokens;
