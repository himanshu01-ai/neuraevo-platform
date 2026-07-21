"use client";

import { motion, useReducedMotion } from "framer-motion";
import { type VoiceState } from "../lib/session-machine";
import { cn } from "@/lib/utils";

/**
 * The AI visualization — a calm, breathing orb whose motion *is* the assistant's
 * state (Sprint 22). Not decoration: each state has its own energy, so a glance
 * says listening vs. thinking vs. speaking without reading a word.
 *
 * Built on the app's framer-motion + reduced-motion convention (like `Reveal`),
 * not the heavy Three.js brand core — it needs to react to state every frame and
 * stay light. Under `prefers-reduced-motion` it renders a still, softly-glowing
 * orb: the state still reads through colour and the status text, never motion
 * alone. It is `aria-hidden`; the live status line is the accessible signal.
 */

interface Energy {
  /** Peak scale of the breathing core. */
  scale: number;
  /** Seconds per breath — lower is more urgent. */
  speed: number;
  /** Whether the outer rings ripple. */
  rings: boolean;
  /** Colour class for the core. */
  core: string;
  /** Glow colour class. */
  glow: string;
}

function energyFor(state: VoiceState): Energy {
  switch (state) {
    case "listening":
      return { scale: 1.1, speed: 2.2, rings: true, core: "bg-primary", glow: "shadow-primary/40" };
    case "understanding":
    case "thinking":
    case "planning":
      return { scale: 1.16, speed: 1.1, rings: true, core: "bg-primary", glow: "shadow-primary/50" };
    case "executing":
      return { scale: 1.16, speed: 0.9, rings: true, core: "bg-primary", glow: "shadow-primary/50" };
    case "speaking":
      return { scale: 1.22, speed: 0.55, rings: true, core: "bg-primary", glow: "shadow-primary/60" };
    case "waiting_permission":
      return { scale: 1.06, speed: 2.8, rings: true, core: "bg-warning", glow: "shadow-warning/40" };
    case "error":
      return { scale: 1.0, speed: 3, rings: false, core: "bg-destructive", glow: "shadow-destructive/40" };
    case "completed":
    case "returning":
      return { scale: 1.08, speed: 2, rings: false, core: "bg-success", glow: "shadow-success/40" };
    default:
      return { scale: 1.04, speed: 3.2, rings: false, core: "bg-primary/80", glow: "shadow-primary/25" };
  }
}

export interface VoiceOrbProps {
  state: VoiceState;
  className?: string;
}

export function VoiceOrb({ state, className }: VoiceOrbProps) {
  const reduce = useReducedMotion() ?? false;
  const energy = energyFor(state);

  const breathe = reduce
    ? {}
    : {
        scale: [1, energy.scale, 1],
        transition: { duration: energy.speed, repeat: Infinity, ease: "easeInOut" as const },
      };

  return (
    <div
      aria-hidden="true"
      className={cn("relative flex items-center justify-center", className)}
    >
      {/* Rippling rings — expanding echoes while the assistant is engaged. */}
      {energy.rings && !reduce
        ? [0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="absolute rounded-full border border-primary/20"
              style={{ width: "72%", height: "72%" }}
              animate={{ scale: [1, 1.9], opacity: [0.5, 0] }}
              transition={{
                duration: energy.speed * 2.2,
                repeat: Infinity,
                ease: "easeOut",
                delay: i * (energy.speed * 0.7),
              }}
            />
          ))
        : null}

      {/* Soft halo. */}
      <div
        className={cn(
          "absolute rounded-full blur-2xl transition-colors duration-700",
          energy.core,
          "opacity-25"
        )}
        style={{ width: "80%", height: "80%" }}
      />

      {/* The core. */}
      <motion.div
        className={cn(
          "relative rounded-full shadow-2xl transition-colors duration-700",
          energy.core,
          energy.glow
        )}
        style={{ width: "48%", height: "48%" }}
        animate={breathe}
      >
        {/* Inner sheen for depth. */}
        <div className="absolute inset-[12%] rounded-full bg-gradient-to-br from-white/40 to-transparent" />
      </motion.div>
    </div>
  );
}
