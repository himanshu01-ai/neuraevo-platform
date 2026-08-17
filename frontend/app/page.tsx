import { SiteShell } from "@/layouts/site-shell";
import { Hero } from "@/components/marketing/hero";
import { FeatureSection } from "@/components/marketing/feature-section";
import { WorkflowSection } from "@/components/marketing/workflow-section";
import { EnterpriseSection } from "@/components/marketing/enterprise-section";
import { CtaSection } from "@/components/marketing/cta-section";

export default function HomePage() {
  return (
    <SiteShell>
      <Hero />
      <FeatureSection />
      <WorkflowSection />
      <EnterpriseSection />
      <CtaSection />
    </SiteShell>
  );
}
