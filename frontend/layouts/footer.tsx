import { Container } from "@/components/layout/container";
import { Logo } from "@/components/brand/logo";
import { siteConfig } from "@/lib/site-config";

const columns = [
  { title: "Product", links: siteConfig.footer.product },
  { title: "Company", links: siteConfig.footer.company },
  { title: "Legal", links: siteConfig.footer.legal },
] as const;

/** Site footer. Static, server-rendered. */
export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t bg-card/40">
      <Container className="py-14">
        <div className="grid gap-10 md:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-4">
            <Logo href="/" />
            <p className="max-w-xs text-sm leading-relaxed text-muted-foreground">
              The voice-first AI employee that plans, executes, and asks for approval — so you can delegate complete work.
            </p>
          </div>

          {columns.map((col) => (
            <nav key={col.title} aria-label={col.title} className="space-y-3">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {col.title}
              </h2>
              <ul className="space-y-2">
                {col.links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className="text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t pt-6 text-sm text-muted-foreground sm:flex-row">
          <p>
            &copy; {year} {siteConfig.name}. All rights reserved.
          </p>
          <p>An AI Employee platform.</p>
        </div>
      </Container>
    </footer>
  );
}
