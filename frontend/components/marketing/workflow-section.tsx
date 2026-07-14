import { Section } from "@/components/layout/section";
import { Container } from "@/components/layout/container";
import { Reveal } from "@/components/motion/reveal";
import { SectionHeading } from "./section-heading";
import { WorkflowPreview } from "./workflow-preview";

/** "How it works" — the visible workflow, not chat. */
export function WorkflowSection() {
  return (
    <Section id="workflow" className="bg-muted/30">
      <Container>
        <Reveal>
          <SectionHeading
            eyebrow="How it works"
            title="Work you can watch, not a conversation"
            description="Every delegated task moves through a transparent pipeline. You see the plan, the execution, and every point where your approval is required."
          />
        </Reveal>
        <Reveal delay={0.1}>
          <WorkflowPreview variant="full" className="mt-16" />
        </Reveal>
      </Container>
    </Section>
  );
}
