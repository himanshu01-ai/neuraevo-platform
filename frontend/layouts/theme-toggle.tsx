"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { useMounted } from "@/hooks/use-mounted";

/** Light/dark toggle. Renders a stable placeholder until mounted to avoid a
 *  hydration mismatch (the server can't know the resolved theme). */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const mounted = useMounted();
  const isDark = resolvedTheme === "dark";

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={mounted ? `Switch to ${isDark ? "light" : "dark"} mode` : "Toggle theme"}
    >
      {mounted ? (
        isDark ? <Sun aria-hidden /> : <Moon aria-hidden />
      ) : (
        <Sun aria-hidden className="opacity-0" />
      )}
    </Button>
  );
}
