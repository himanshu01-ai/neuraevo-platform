"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Grid } from "./grid";

/**
 * Full-page ambient background: a decorative grid plus two slow floating violet
 * gradient blobs (primary token). Fixed behind all content; static under
 * prefers-reduced-motion.
 */
export function Background() {
  const reduce = useReducedMotion();

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <Grid className="opacity-50" />
      <motion.div
        className="absolute -left-40 -top-40 size-[42rem] rounded-full bg-primary/20 blur-3xl"
        animate={reduce ? undefined : { x: [0, 40, 0], y: [0, 30, 0] }}
        transition={reduce ? undefined : { duration: 20, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute -right-40 top-1/3 size-[34rem] rounded-full bg-primary/10 blur-3xl"
        animate={reduce ? undefined : { x: [0, -30, 0], y: [0, 40, 0] }}
        transition={reduce ? undefined : { duration: 26, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}
