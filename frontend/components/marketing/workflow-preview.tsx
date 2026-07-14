"use client";

import { motion, useReducedMotion } from "framer-motion";
import { siteConfig } from "@/lib/site-config";
import { cn } from "@/lib/utils";

export interface WorkflowPreviewProps {
  /** `full` shows step descriptions; `compact` is icon + label only. */
  variant?: "full" | "compact";
  className?: string;
}

/**
 * The signature flow — Task → Planning → Execution → Approvals → Memory →
 * Results — as a responsive stepper (vertical on mobile, horizontal on
 * desktop) with a sequential node pulse. Static under reduced motion.
 */
export function WorkflowPreview({ variant = "full", className }: WorkflowPreviewProps) {
  const reduce = useReducedMotion();
  const steps = siteConfig.workflow;

  return (
    <ol className={cn("relative grid gap-8 lg:grid-cols-6 lg:gap-4", className)}>
      {steps.map((s, i) => {
        const Icon = s.icon;
        const isLast = i === steps.length - 1;
        return (
          <li
            key={s.title}
            className="relative flex items-start gap-4 lg:flex-col lg:items-center lg:gap-0 lg:text-center"
          >
            {/* connector — mobile (vertical) */}
            {!isLast && (
              <span
                aria-hidden
                className="absolute left-5 top-11 h-[calc(100%+1rem)] w-px bg-border lg:hidden"
              />
            )}
            {/* connector — desktop (horizontal) */}
            {!isLast && (
              <span
                aria-hidden
                className="absolute right-0 top-5 hidden h-px w-full translate-x-1/2 bg-border lg:block"
              />
            )}

            <div className="relative z-10 flex size-10 shrink-0 items-center justify-center rounded-full border bg-card text-primary shadow-sm">
              <Icon className="size-5" aria-hidden />
              {!reduce && (
                <motion.span
                  aria-hidden
                  className="absolute inset-0 rounded-full ring-2 ring-primary/40"
                  animate={{ opacity: [0, 0.7, 0], scale: [1, 1.4, 1.4] }}
                  transition={{ duration: 3, repeat: Infinity, ease: "easeOut", delay: i * 0.4 }}
                />
              )}
            </div>

            <div className="lg:mt-4">
              <div className="font-mono text-xs text-muted-foreground">{s.step}</div>
              <div className="font-semibold text-foreground">{s.title}</div>
              {variant === "full" && (
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground lg:mx-auto lg:max-w-[16ch]">
                  {s.description}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
