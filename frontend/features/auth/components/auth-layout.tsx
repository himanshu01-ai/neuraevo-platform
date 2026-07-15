import type { ReactNode } from "react";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/layouts/theme-toggle";
import { AuthBrandPanel } from "./auth-brand-panel";

/** Split-screen auth shell: form column (left) + brand panel (right, ≥ lg). */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="relative flex flex-col">
        <header className="flex items-center justify-between gap-4 p-4 sm:p-6">
          <Logo variant="wordmark" href="/" className="lg:invisible" />
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" href="/">
              <ArrowLeft className="size-4" aria-hidden="true" />
              Home
            </Button>
            <ThemeToggle />
          </div>
        </header>
        <main className="flex flex-1 items-center justify-center px-4 pb-16 pt-6 sm:px-6">
          {children}
        </main>
      </div>
      <AuthBrandPanel />
    </div>
  );
}
