import { LogoMark } from "@/components/brand/logo";

export default function Loading() {
  return (
    <div className="flex min-h-dvh items-center justify-center">
      <LogoMark className="size-12 animate-pulse text-foreground" />
      <span className="sr-only">Loading</span>
    </div>
  );
}
