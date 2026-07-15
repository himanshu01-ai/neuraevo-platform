import { z } from "zod";

export const profileSchema = z.object({
  fullName: z.string().min(2, "Enter your name"),
  role: z.string().min(1, "Select your role"),
});

export const companySchema = z.object({
  companyName: z.string().min(1, "Enter your company name"),
  companySize: z.string().min(1, "Select company size"),
  industry: z.string().min(1, "Select an industry"),
});

export const aiPreferencesSchema = z.object({
  aiTone: z.string().min(1, "Choose a communication style"),
  aiAutonomy: z.string().min(1, "Choose an autonomy level"),
  aiCapabilities: z.array(z.string()).min(1, "Enable at least one capability"),
});

export const workspacePreferencesSchema = z.object({
  density: z.string().min(1, "Choose a layout density"),
  notifications: z.array(z.string()),
});

export type ProfileValues = z.infer<typeof profileSchema>;
export type CompanyValues = z.infer<typeof companySchema>;
export type AiPreferencesValues = z.infer<typeof aiPreferencesSchema>;
export type WorkspacePreferencesValues = z.infer<typeof workspacePreferencesSchema>;
