"use client";

import { Check } from "lucide-react";
import type { EmployeeAccent, EmployeeGlyph } from "@/services/employees";
import { ACCENT_LIST, GLYPH_LIST } from "../models/employee-appearance";
import { EmployeeAvatar } from "../components/employee-avatar";
import { cn } from "@/lib/utils";

export interface AppearancePickerProps {
  name: string;
  accent: EmployeeAccent;
  glyph: EmployeeGlyph;
  onAccentChange: (accent: EmployeeAccent) => void;
  onGlyphChange: (glyph: EmployeeGlyph) => void;
}

/**
 * How the employee will look: its accent and its avatar glyph, previewed live.
 *
 * Both are radio groups rather than lists of buttons — picking one of several is
 * what a radio group is, and it gets arrow-key navigation and grouping for free.
 * The swatch is decorative; each control is named in text for anyone who can't
 * tell the colours apart.
 */
export function AppearancePicker({
  name,
  accent,
  glyph,
  onAccentChange,
  onGlyphChange,
}: AppearancePickerProps) {
  return (
    <div className="space-y-5">
      <div className="flex items-center gap-4 rounded-lg border bg-background p-4">
        <EmployeeAvatar name={name || "New employee"} accent={accent} glyph={glyph} size="lg" />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-foreground">{name || "New employee"}</p>
          <p className="text-xs text-muted-foreground">This is how it will appear in the directory.</p>
        </div>
      </div>

      <fieldset>
        <legend className="mb-2 text-sm font-medium text-foreground">Colour</legend>
        <div className="flex flex-wrap gap-2">
          {ACCENT_LIST.map((meta) => (
            <label
              key={meta.accent}
              className={cn(
                "relative inline-flex cursor-pointer items-center justify-center rounded-full transition-all",
                "focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background",
                "has-[:checked]:ring-2 has-[:checked]:ring-primary has-[:checked]:ring-offset-2 has-[:checked]:ring-offset-background"
              )}
            >
              <input
                type="radio"
                name="employee-accent"
                value={meta.accent}
                checked={accent === meta.accent}
                onChange={() => onAccentChange(meta.accent)}
                className="peer sr-only"
              />
              <span
                aria-hidden="true"
                className={cn(
                  "inline-flex size-8 items-center justify-center rounded-full text-primary-foreground",
                  meta.swatch
                )}
              >
                <Check
                  className="size-4 opacity-0 transition-opacity peer-checked:opacity-100"
                  strokeWidth={3}
                />
              </span>
              <span className="sr-only">{meta.label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="mb-2 text-sm font-medium text-foreground">Avatar</legend>
        <div className="flex flex-wrap gap-2">
          {GLYPH_LIST.map((meta) => {
            const Icon = meta.icon;
            return (
              <label
                key={meta.glyph}
                className={cn(
                  "inline-flex cursor-pointer items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
                  "hover:border-primary/40",
                  "focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1 focus-within:ring-offset-background",
                  "has-[:checked]:border-primary has-[:checked]:bg-primary/5 has-[:checked]:text-foreground",
                  "text-muted-foreground"
                )}
              >
                <input
                  type="radio"
                  name="employee-glyph"
                  value={meta.glyph}
                  checked={glyph === meta.glyph}
                  onChange={() => onGlyphChange(meta.glyph)}
                  className="sr-only"
                />
                {Icon ? <Icon className="size-3.5" aria-hidden="true" /> : null}
                {meta.label}
              </label>
            );
          })}
        </div>
      </fieldset>
    </div>
  );
}
