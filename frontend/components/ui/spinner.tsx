import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

/** Indeterminate spinner. Collapses to a static icon under reduced motion
 *  (global rule in styles/globals.css). Pair with a visible/AT label. */
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin", className)} aria-hidden="true" />;
}
