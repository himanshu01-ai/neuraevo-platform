"use client";

import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { Container } from "@/components/layout/container";
import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "./theme-toggle";
import { MobileNav } from "./mobile-nav";
import { siteConfig } from "@/lib/site-config";
import { cn } from "@/lib/utils";

/** Sticky, responsive top navigation. Turns to a glass surface on scroll. */
export function Navbar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "sticky top-0 z-header w-full border-b transition-colors duration-200",
        scrolled ? "surface-glass border-border" : "border-transparent bg-transparent"
      )}
    >
      <Container>
        <nav className="flex h-14 items-center justify-between gap-4" aria-label="Main">
          <Logo href="/" />

          <ul className="hidden items-center gap-1 md:flex">
            {siteConfig.nav.map((item) => (
              <li key={item.href}>
                <a
                  href={item.href}
                  className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>

          <div className="hidden items-center gap-2 md:flex">
            <ThemeToggle />
            <Button size="sm" href={siteConfig.primaryCta.href}>
              {siteConfig.primaryCta.label}
            </Button>
          </div>

          <div className="flex items-center gap-1 md:hidden">
            <ThemeToggle />
            <Button
              variant="ghost"
              size="icon"
              aria-label="Open menu"
              aria-expanded={open}
              aria-controls="mobile-nav"
              onClick={() => setOpen(true)}
            >
              <Menu aria-hidden />
            </Button>
          </div>
        </nav>
      </Container>

      <MobileNav open={open} onClose={() => setOpen(false)} />
    </header>
  );
}
