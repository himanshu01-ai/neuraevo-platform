import { Section } from "@/components/layout/section";
import { Container } from "@/components/layout/container";
import { Reveal } from "@/components/motion/reveal";
import { SectionHeading } from "./section-heading";
import { FeatureCard } from "./feature-card";
import { siteConfig } from "@/lib/site-config";

/** "What it can do" — the six executable capabilities as reusable cards. */
export function FeatureSection() {
  return (
    <Section id="capabilities">
      <Container>
        <Reveal>
          <SectionHeading
            eyebrow="Capabilities"
            title="One employee. Every tool."
            description="NeuraEvo executes real work across the tools you already use — each capability isolated behind a single, safe execution contract."
          />
        </Reveal>
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {siteConfig.capabilities.map((c, i) => (
            <Reveal key={c.title} delay={i * 0.05}>
              <FeatureCard title={c.title} description={c.description} icon={c.icon} />
            </Reveal>
          ))}
        </div>
      </Container>
    </Section>
  );
}
