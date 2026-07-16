import { Avatar } from "@/components/ui/avatar";
import type { EmployeeAccent, EmployeeGlyph } from "@/services/employees";
import { ACCENT_META, GLYPH_META } from "../models/employee-appearance";
import { cn } from "@/lib/utils";

export type EmployeeAvatarSize = "sm" | "md" | "lg";

export interface EmployeeAvatarProps {
  name: string;
  accent: EmployeeAccent;
  glyph: EmployeeGlyph;
  size?: EmployeeAvatarSize;
  className?: string;
}

const SIZES: Record<EmployeeAvatarSize, { container: string; icon: string }> = {
  sm: { container: "size-8 text-xs", icon: "size-4" },
  md: { container: "size-10 text-sm", icon: "size-5" },
  lg: { container: "size-14 text-md", icon: "size-6" },
};

/**
 * An employee's face: its accent tint, and either a chosen glyph or its
 * initials. The initials case defers to the shared <Avatar> primitive rather
 * than restating how initials are derived.
 *
 * Decorative in both cases — the employee's name is always adjacent in the
 * markup, so the avatar stays out of the accessibility tree.
 */
export function EmployeeAvatar({ name, accent, glyph, size = "sm", className }: EmployeeAvatarProps) {
  const { surface } = ACCENT_META[accent];
  const { icon: Icon } = GLYPH_META[glyph];
  const dimensions = SIZES[size];

  if (!Icon) {
    return <Avatar name={name} className={cn(dimensions.container, surface, className)} />;
  }

  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex shrink-0 select-none items-center justify-center rounded-full",
        dimensions.container,
        surface,
        className
      )}
    >
      <Icon className={dimensions.icon} />
    </span>
  );
}
