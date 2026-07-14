import type { ReactNode } from "react";
import { Navbar } from "./navbar";
import { Footer } from "./footer";
import { Background } from "@/components/marketing/background";

/**
 * The reusable landing/marketing application shell: ambient background,
 * skip-to-content link, sticky Navbar, main region, and Footer. Page content is
 * rendered inside <main>.
 */
export function SiteShell({ children }: { children: ReactNode }) {
  return (
    <>
      <Background />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-tooltip focus:rounded-md focus:bg-card focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        Skip to content
      </a>
      <Navbar />
      <main id="main">{children}</main>
      <Footer />
    </>
  );
}
