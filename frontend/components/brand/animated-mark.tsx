"use client";

import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

const NODES = [
  { cx: 28, cy: 26, r: 2.6 },
  { cx: 39, cy: 38, r: 3.7 },
  { cx: 50, cy: 50, r: 5 },
  { cx: 61, cy: 62, r: 6.4 },
] as const;

/**
 * Animated hero variant of the mark: the node chain draws in and then pulses
 * down the diagonal. Fully static under prefers-reduced-motion.
 */
export function AnimatedMark({ className }: { className?: string }) {
  const reduce = useReducedMotion();

  return (
    <svg viewBox="0 0 100 100" fill="none" className={cn("size-40", className)} role="img" aria-label="NeuraEvo">
      <line x1="28" y1="26" x2="28" y2="74" className="stroke-current" strokeWidth="2.6" strokeLinecap="round" />
      <line x1="72" y1="26" x2="72" y2="74" className="stroke-current" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="72" cy="26" r="4" className="stroke-current" strokeWidth="2" />
      <circle cx="28" cy="74" r="4" className="stroke-current" strokeWidth="2" />

      <line x1="28" y1="26" x2="72" y2="74" className="stroke-primary" strokeWidth="7" strokeLinecap="round" opacity="0.14" />
      <line x1="28" y1="26" x2="72" y2="74" className="stroke-primary" strokeWidth="1.8" strokeLinecap="round" opacity="0.55" />

      {NODES.map((n, i) => (
        <motion.circle
          key={i}
          cx={n.cx}
          cy={n.cy}
          r={n.r}
          className="fill-primary"
          initial={reduce ? undefined : { scale: 0.6, opacity: 0.5 }}
          animate={reduce ? undefined : { scale: [0.85, 1.1, 0.85], opacity: [0.7, 1, 0.7] }}
          transition={reduce ? undefined : { duration: 2.4, repeat: Infinity, ease: "easeInOut", delay: i * 0.25 }}
          style={{ transformOrigin: `${n.cx}px ${n.cy}px` }}
        />
      ))}

      <circle cx="72" cy="74" r="13" className="fill-primary" opacity="0.16" />
      <motion.circle
        cx="72"
        cy="74"
        r="8.4"
        className="fill-primary"
        animate={reduce ? undefined : { scale: [1, 1.08, 1] }}
        transition={reduce ? undefined : { duration: 2.4, repeat: Infinity, ease: "easeInOut", delay: 1 }}
        style={{ transformOrigin: "72px 74px" }}
      />
    </svg>
  );
}
