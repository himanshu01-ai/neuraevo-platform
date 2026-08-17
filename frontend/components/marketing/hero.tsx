"use client";

import dynamic from "next/dynamic";
import { Sparkles, ArrowRight } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { Container } from "@/components/layout/container";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Reveal } from "@/components/motion/reveal";
import { AnimatedMark } from "@/components/brand/animated-mark";
import { WorkflowPreview } from "./workflow-preview";
import { siteConfig } from "@/lib/site-config";

/** The 3D AI Core is lazy, client-only, and never blocks first paint. */
const AiCore = dynamic(() => import("@/components/brand/ai-core"), {
  ssr: false,
  loading: () => <div aria-hidden className="size-full rounded-full bg-primary/10 blur-2xl" />,
});

export function Hero() {
  const reduce = useReducedMotion();

  return (
    <section className="relative overflow-hidden pb-16 pt-28 sm:pt-36">
      <Container>
        <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-8">
          {/* Copy */}
          <div className="text-center lg:text-left">
            <Reveal>
              <Badge variant="primary">
                <Sparkles className="size-3.5" aria-hidden />
                Voice-first AI Employee
              </Badge>
            </Reveal>
            <Reveal delay={0.05}>
              <h1 className="mt-6 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                Delegate the work.
                <br />
                <span className="text-primary">Not just the chat.</span>
              </h1>
            </Reveal>
            <Reveal delay={0.1}>
              <p className="mx-auto mt-6 max-w-xl text-md text-muted-foreground sm:text-lg lg:mx-0">
                {siteConfig.description}
              </p>
            </Reveal>
            <Reveal delay={0.15}>
              <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row lg:justify-start">
                <Button size="lg" href={siteConfig.primaryCta.href} className="w-full sm:w-auto">
                  {siteConfig.primaryCta.label}
                  <ArrowRight className="size-4" aria-hidden />
                </Button>
                <Button size="lg" variant="outline" href={siteConfig.secondaryCta.href} className="w-full sm:w-auto">
                  {siteConfig.secondaryCta.label}
                </Button>
              </div>
            </Reveal>
          </div>

          {/* Visual: 3D network with the animated mark at its core */}
          <div className="relative mx-auto aspect-square w-full max-w-md lg:max-w-none">
            <div
              aria-hidden
              className="absolute inset-0 rounded-full bg-primary/10 blur-3xl"
            />
            <div className="absolute inset-0">
              <AiCore />
            </div>
            <motion.div
              className="absolute inset-0 flex items-center justify-center"
              initial={reduce ? undefined : { opacity: 0, scale: 0.9 }}
              animate={reduce ? undefined : { opacity: 1, scale: 1 }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            >
              <AnimatedMark className="size-32 drop-shadow-[0_8px_24px_hsl(var(--primary)/0.35)] sm:size-40" />
            </motion.div>
          </div>
        </div>

        {/* Signature workflow */}
        <Reveal delay={0.1}>
          <div className="mt-20 rounded-xl border bg-card/60 p-6 shadow-sm backdrop-blur-sm sm:p-8">
            <p className="mb-8 text-center font-mono text-xs uppercase tracking-wider text-muted-foreground">
              Task → Planning → Execution → Approvals → Memory → Results
            </p>
            <WorkflowPreview variant="compact" />
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
