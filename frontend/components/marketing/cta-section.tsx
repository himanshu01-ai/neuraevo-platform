import { Section } from "@/components/layout/section";
import { Container } from "@/components/layout/container";
import { Reveal } from "@/components/motion/reveal";
import { Button } from "@/components/ui/button";
import { siteConfig } from "@/lib/site-config";

/** Final call to action. */
export function CtaSection() {
  return (
    <Section id="get-started">
      <Container>
        <Reveal>
          <div className="relative overflow-hidden rounded-xl border bg-card px-6 py-16 text-center shadow-sm sm:px-16">
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/15 via-transparent to-primary/10"
            />
            <div className="relative mx-auto max-w-2xl space-y-6">
              <h2 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                Delegate your first task
              </h2>
              <p className="text-md text-muted-foreground">
                Give NeuraEvo real work and watch it plan, execute, and check in for approval — the way an employee would.
              </p>
              <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Button size="lg" href={siteConfig.primaryCta.href}>
                  {siteConfig.primaryCta.label}
                </Button>
                <Button size="lg" variant="outline" href="#capabilities">
                  Explore capabilities
                </Button>
              </div>
            </div>
          </div>
        </Reveal>
      </Container>
    </Section>
  );
}
