import { create } from "zustand";
import type {
  EmployeeAccent,
  EmployeeCapability,
  EmployeeConfiguration,
  EmployeeDetail,
  EmployeeDraft,
  EmployeeGlyph,
  EmployeeRole,
  EmployeeTemplate,
} from "@/services/employees";

/**
 * The employee builder's client state: the draft being authored.
 *
 * On the "server data is never mirrored into Zustand" rule (docs/09): this holds
 * a *draft*, not a cache. The saved employee stays in the Query cache; opening
 * the builder copies it once into an editing buffer the user then owns — the
 * same relationship a form has with the record it edits. `hydrate` refuses to
 * overwrite a draft for an employee already loaded, so a background refetch can
 * never discard your edits.
 *
 * It is separate from `directory-store` because browsing a roster and authoring
 * one employee are different jobs on different screens; sharing a store would
 * couple a filter change to an unsaved draft for no gain.
 *
 * Nothing here executes anything. It describes an employee.
 */

export const DEFAULT_CONFIGURATION: EmployeeConfiguration = {
  autonomy: "balanced",
  tone: "professional",
  executionMode: "SEQUENTIAL",
  priority: "MEDIUM",
  requireApproval: true,
  language: "en",
};

interface BuilderState {
  /** `null` while creating; the employee's id once it exists. */
  employeeId: string | null;
  /** The template this draft started from, for the builder's summary line. */
  templateId: string | null;
  name: string;
  role: EmployeeRole;
  customRole: string;
  description: string;
  behaviorSummary: string;
  accent: EmployeeAccent;
  glyph: EmployeeGlyph;
  capabilities: EmployeeCapability[];
  configuration: EmployeeConfiguration;
  isDirty: boolean;

  hydrate: (detail: EmployeeDetail) => void;
  resetDraft: () => void;
  applyTemplate: (template: EmployeeTemplate) => void;
  setName: (name: string) => void;
  setRole: (role: EmployeeRole) => void;
  setCustomRole: (customRole: string) => void;
  setDescription: (description: string) => void;
  setBehaviorSummary: (behaviorSummary: string) => void;
  setAccent: (accent: EmployeeAccent) => void;
  setGlyph: (glyph: EmployeeGlyph) => void;
  toggleCapability: (capability: EmployeeCapability) => void;
  setConfiguration: (patch: Partial<EmployeeConfiguration>) => void;
  markSaved: (id: string) => void;
}

const EMPTY = {
  employeeId: null,
  templateId: null,
  name: "",
  role: "CUSTOM" as EmployeeRole,
  customRole: "",
  description: "",
  behaviorSummary: "",
  accent: "violet" as EmployeeAccent,
  glyph: "initials" as EmployeeGlyph,
  capabilities: [] as EmployeeCapability[],
  configuration: DEFAULT_CONFIGURATION,
  isDirty: false,
};

export const useEmployeeBuilderStore = create<BuilderState>()((set, get) => ({
  ...EMPTY,

  hydrate: (detail) => {
    // Refuse to clobber an in-progress draft for the same employee: a refetch
    // must never throw away edits.
    if (get().employeeId === detail.id) return;
    set({
      employeeId: detail.id,
      templateId: null,
      name: detail.name,
      role: detail.role,
      customRole: detail.customRole,
      description: detail.description,
      behaviorSummary: detail.behaviorSummary,
      accent: detail.accent,
      glyph: detail.glyph,
      capabilities: [...detail.capabilities],
      configuration: { ...detail.configuration },
      isDirty: false,
    });
  },

  resetDraft: () => set({ ...EMPTY }),

  /**
   * Fills the draft from a template. This is a starting point, not a link: once
   * applied, the draft is the user's, and editing it never writes back.
   */
  applyTemplate: (template) =>
    set({
      employeeId: null,
      templateId: template.id,
      name: "",
      role: template.role,
      customRole: "",
      description: template.description,
      behaviorSummary: template.behaviorSummary,
      accent: template.accent,
      glyph: template.glyph,
      capabilities: [...template.capabilities],
      configuration: { ...template.configuration },
      isDirty: false,
    }),

  setName: (name) => set({ name, isDirty: true }),
  setRole: (role) => set({ role, isDirty: true }),
  setCustomRole: (customRole) => set({ customRole, isDirty: true }),
  setDescription: (description) => set({ description, isDirty: true }),
  setBehaviorSummary: (behaviorSummary) => set({ behaviorSummary, isDirty: true }),
  setAccent: (accent) => set({ accent, isDirty: true }),
  setGlyph: (glyph) => set({ glyph, isDirty: true }),

  toggleCapability: (capability) =>
    set((s) => ({
      capabilities: s.capabilities.includes(capability)
        ? s.capabilities.filter((c) => c !== capability)
        : [...s.capabilities, capability],
      isDirty: true,
    })),

  setConfiguration: (patch) =>
    set((s) => ({ configuration: { ...s.configuration, ...patch }, isDirty: true })),

  markSaved: (id) => set({ employeeId: id, isDirty: false }),
}));

/**
 * The draft as the service takes it. Kept out of the store so the store holds
 * state and the caller decides when to serialise — the builder's save is the
 * only place this shape is needed.
 */
export function toEmployeeDraft(state: BuilderState): EmployeeDraft {
  return {
    id: state.employeeId,
    name: state.name,
    role: state.role,
    customRole: state.customRole,
    description: state.description,
    behaviorSummary: state.behaviorSummary,
    accent: state.accent,
    glyph: state.glyph,
    capabilities: state.capabilities,
    configuration: state.configuration,
  };
}
