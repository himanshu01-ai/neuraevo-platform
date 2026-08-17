"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/brand/logo";
import { siteConfig } from "@/lib/site-config";

export interface MobileNavProps {
  open: boolean;
  onClose: () => void;
}

/** Accessible mobile menu sheet: focus moves in on open, Esc + scrim close,
 *  body scroll locked while open. */
export function MobileNav({ open, onClose }: MobileNavProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    const t = window.setTimeout(
      () => panelRef.current?.querySelector<HTMLElement>("a, button")?.focus(),
      60
    );
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      window.clearTimeout(t);
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          id="mobile-nav"
          role="dialog"
          aria-modal="true"
          aria-label="Menu"
          className="fixed inset-0 z-modal md:hidden"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <button
            aria-label="Close menu"
            tabIndex={-1}
            className="absolute inset-0 cursor-default bg-background/80 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            ref={panelRef}
            className="absolute inset-x-0 top-0 border-b bg-background p-4 shadow-lg"
            initial={{ y: -16, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -16, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="flex items-center justify-between">
              <Logo href="/" />
              <Button variant="ghost" size="icon" aria-label="Close menu" onClick={onClose}>
                <X aria-hidden />
              </Button>
            </div>
            <ul className="mt-6 space-y-1">
              {siteConfig.nav.map((item) => (
                <li key={item.href}>
                  <a
                    href={item.href}
                    onClick={onClose}
                    className="block rounded-md px-3 py-3 text-base font-medium text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
            <div className="mt-6">
              <Button href={siteConfig.primaryCta.href} onClick={onClose} className="w-full">
                {siteConfig.primaryCta.label}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
