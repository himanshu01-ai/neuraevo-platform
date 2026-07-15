import { ShieldCheck, Workflow, Brain } from "lucide-react";
import { Logo } from "@/components/brand/logo";
import { AnimatedMark } from "@/components/brand/animated-mark";
import { Grid } from "@/components/marketing/grid";
import { siteConfig } from "@/lib/site-config";

const points = [
  { icon: Workflow, text: "Plans and executes real work across your tools" },
  { icon: ShieldCheck, text: "Pauses for your approval on anything irreversible" },
  { icon: Brain, text: "Remembers only through approved architecture" },
];

/** Premium side panel shown next to the auth forms on large screens. */
export function AuthBrandPanel() {
  const year = new Date().getFullYear();
  return (
    <div className="relative hidden overflow-hidden bg-muted/30 lg:flex lg:flex-col lg:justify-between lg:p-12">
      <Grid className="opacity-40" />
      <div aria-hidden="true" className="absolute -right-24 top-1/4 size-96 rounded-full bg-primary/20 blur-3xl" />

      <Logo variant="wordmark" href="/" className="relative" />

      <div className="relative max-w-sm space-y-6">
        <AnimatedMark className="size-16" />
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">
          Configure your AI employee
        </h2>
        <p className="text-sm leading-relaxed text-muted-foreground">{siteConfig.description}</p>
        <ul className="space-y-3">
          {points.map((p) => (
            <li key={p.text} className="flex items-start gap-3 text-sm text-foreground">
              <span className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                <p.icon className="size-3.5" aria-hidden="true" />
              </span>
              {p.text}
            </li>
          ))}
        </ul>
      </div>

      <p className="relative text-xs text-muted-foreground">
        &copy; {year} {siteConfig.name}. An AI Employee platform.
      </p>
    </div>
  );
}
