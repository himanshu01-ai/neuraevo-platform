import Link from "next/link";
import { cn } from "@/lib/utils";
import { siteConfig } from "@/lib/site-config";

/** Node chain of the official mark (violet, mapped to the primary token). */
const NODES = [
  { cx: 28, cy: 26, r: 2.6 },
  { cx: 39, cy: 38, r: 3.7 },
  { cx: 50, cy: 50, r: 5 },
  { cx: 61, cy: 62, r: 6.4 },
] as const;

/**
 * The official NeuraEvo mark as inline SVG. Structure inherits `currentColor`
 * (theme-adaptive); the node chain uses the `primary` token — which is the
 * official logo violet (#6C5CF2). Size with `className` (e.g. `size-8`).
 */
export function LogoMark({ className, ...props }: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 100 100" fill="none" className={cn("size-8", className)} aria-hidden {...props}>
      <line x1="28" y1="26" x2="28" y2="74" className="stroke-current" strokeWidth="2.6" strokeLinecap="round" />
      <line x1="72" y1="26" x2="72" y2="74" className="stroke-current" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="72" cy="26" r="4" className="stroke-current" strokeWidth="2" />
      <circle cx="28" cy="74" r="4" className="stroke-current" strokeWidth="2" />
      <line x1="28" y1="26" x2="72" y2="74" className="stroke-primary" strokeWidth="7" strokeLinecap="round" opacity="0.14" />
      <line x1="28" y1="26" x2="72" y2="74" className="stroke-primary" strokeWidth="1.8" strokeLinecap="round" opacity="0.55" />
      {NODES.map((n, i) => (
        <circle key={i} cx={n.cx} cy={n.cy} r={n.r} className="fill-primary" />
      ))}
      <circle cx="72" cy="74" r="13" className="fill-primary" opacity="0.16" />
      <circle cx="72" cy="74" r="8.4" className="fill-primary" />
    </svg>
  );
}

export interface LogoProps {
  variant?: "mark" | "wordmark";
  className?: string;
  /** When set, the whole logo is a link (defaults to home when `asLink`). */
  href?: string;
  markClassName?: string;
}

/** Brand lockup. `wordmark` = mark + product name in the brand typeface. */
export function Logo({ variant = "wordmark", className, href, markClassName }: LogoProps) {
  const content =
    variant === "mark" ? (
      <>
        <LogoMark className={markClassName} />
        <span className="sr-only">{siteConfig.name}</span>
      </>
    ) : (
      <>
        <LogoMark className={cn("size-7", markClassName)} />
        <span className="text-lg font-semibold tracking-tight text-foreground">{siteConfig.name}</span>
      </>
    );

  const classes = cn("inline-flex items-center gap-2", className);

  if (href) {
    return (
      <Link href={href} className={cn(classes, "rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring")}>
        {content}
      </Link>
    );
  }
  return <span className={classes}>{content}</span>;
}
