import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * `cn` — the canonical className combiner used across the design system and
 * every shadcn/ui component. Merges conditional classes (clsx) and resolves
 * Tailwind conflicts (tailwind-merge) so later utilities win.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
