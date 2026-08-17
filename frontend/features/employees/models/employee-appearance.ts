import {
  Bot,
  Brain,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  Code,
  Headset,
  PenLine,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import {
  EMPLOYEE_ACCENTS,
  EMPLOYEE_GLYPHS,
  type EmployeeAccent,
  type EmployeeGlyph,
} from "@/services/employees";

/**
 * How an employee looks: its accent and its avatar glyph.
 *
 * On colour: these are names for tones the theme already ships — every class
 * below resolves to an existing token, and no new colour is introduced. Colour
 * in this system carries status, so an accent is confined to the avatar and the
 * picker swatch. Status always renders as a labelled badge with a dot, never as
 * colour alone, so a green avatar can't be misread as "healthy".
 */

export interface AccentMeta {
  accent: EmployeeAccent;
  label: string;
  /** Tinted surface for the avatar: soft background + matching foreground. */
  surface: string;
  /** Solid fill for the picker swatch. */
  swatch: string;
}

export const ACCENT_META: Record<EmployeeAccent, AccentMeta> = {
  violet: { accent: "violet", label: "Violet", surface: "bg-primary/10 text-primary", swatch: "bg-primary" },
  blue: { accent: "blue", label: "Blue", surface: "bg-info/10 text-info", swatch: "bg-info" },
  emerald: { accent: "emerald", label: "Emerald", surface: "bg-success/10 text-success", swatch: "bg-success" },
  amber: { accent: "amber", label: "Amber", surface: "bg-warning/10 text-warning", swatch: "bg-warning" },
  rose: { accent: "rose", label: "Rose", surface: "bg-destructive/10 text-destructive", swatch: "bg-destructive" },
  slate: { accent: "slate", label: "Slate", surface: "bg-muted text-muted-foreground", swatch: "bg-muted-foreground" },
};

export const ACCENT_LIST: readonly AccentMeta[] = EMPLOYEE_ACCENTS.map((accent) => ACCENT_META[accent]);

export interface GlyphMeta {
  glyph: EmployeeGlyph;
  label: string;
  /** `null` for `initials`, which defers to the shared <Avatar> primitive. */
  icon: LucideIcon | null;
}

export const GLYPH_META: Record<EmployeeGlyph, GlyphMeta> = {
  initials: { glyph: "initials", label: "Initials", icon: null },
  bot: { glyph: "bot", label: "Bot", icon: Bot },
  brain: { glyph: "brain", label: "Brain", icon: Brain },
  code: { glyph: "code", label: "Code", icon: Code },
  chart: { glyph: "chart", label: "Chart", icon: ChartNoAxesCombined },
  pen: { glyph: "pen", label: "Pen", icon: PenLine },
  headset: { glyph: "headset", label: "Headset", icon: Headset },
  briefcase: { glyph: "briefcase", label: "Briefcase", icon: BriefcaseBusiness },
  sparkles: { glyph: "sparkles", label: "Sparkles", icon: Sparkles },
};

export const GLYPH_LIST: readonly GlyphMeta[] = EMPLOYEE_GLYPHS.map((glyph) => GLYPH_META[glyph]);
