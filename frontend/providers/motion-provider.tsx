"use client";

import { MotionConfig } from "framer-motion";
import type { ReactNode } from "react";

/**
 * Global Framer Motion configuration. `reducedMotion="user"` makes every
 * transform/layout animation collapse when the OS requests reduced motion —
 * the design-system's motion contract (docs/03-motion-guidelines.md).
 */
export function MotionProvider({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
