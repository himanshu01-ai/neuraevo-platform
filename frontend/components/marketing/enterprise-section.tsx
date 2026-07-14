import { Section } from "@/components/layout/section";
import { Container } from "@/components/layout/container";
import { Reveal } from "@/components/motion/reveal";
import { SectionHeading } from "./section-heading";
import { FeatureCard } from "./feature-card";
import { siteConfig } from "@/lib/site-config";

/** "Enterprise" — platform strengths that make delegation trustworthy. */
export function EnterpriseSection() {
  return (
    <Section id="enterprise">
      <Container>
        <Reveal>
          <SectionHeading
            eyebrow="Enterprise-grade"
            title="Built to be trusted with real work"
            description="Deterministic, auditable, and provider-independent — engineered like infrastructure, not a chatbot."
          />
        </Reveal>
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {siteConfig.enterprise.map((e, i) => (
            <Reveal key={e.title} delay={i * 0.05}>
              <FeatureCard title={e.title} description={e.description} icon={e.icon} />
            </Reveal>
          ))}
        </div>
      </Container>
    </Section>
  );
}
