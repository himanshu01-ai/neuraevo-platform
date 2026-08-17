import { cn } from "@/lib/utils";

const sizes = {
  prose: "max-w-prose", //   reading column
  content: "max-w-6xl", //   standard app content (~1152px)
  wide: "max-w-[90rem]", //  dashboards / wide sections (1440px)
  full: "max-w-none", //     edge-to-edge
} as const;

export interface ContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: keyof typeof sizes;
}

/** Centers content with the standard app gutters. Width by semantic role. */
export function Container({ size = "content", className, ...props }: ContainerProps) {
  return (
    <div className={cn("mx-auto w-full px-4 sm:px-6 lg:px-8", sizes[size], className)} {...props} />
  );
}
