import { Button } from "@/components/ui/button";
import { LogoMark } from "@/components/brand/logo";

export default function NotFound() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 px-6 text-center">
      <LogoMark className="size-12 text-foreground" />
      <div className="space-y-2">
        <p className="font-mono text-sm font-semibold text-primary">404</p>
        <h1 className="text-2xl font-semibold text-foreground">Page not found</h1>
        <p className="max-w-md text-muted-foreground">
          The page you&rsquo;re looking for doesn&rsquo;t exist or has moved.
        </p>
      </div>
      <Button href="/">Back to home</Button>
    </div>
  );
}
