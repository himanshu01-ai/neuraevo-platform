import { z } from "zod";

export const emailSchema = z
  .string()
  .min(1, "Email is required")
  .email("Enter a valid email address");

export const strongPasswordSchema = z
  .string()
  .min(8, "Use at least 8 characters")
  .regex(/[a-z]/, "Add a lowercase letter")
  .regex(/[A-Z]/, "Add an uppercase letter")
  .regex(/[0-9]/, "Add a number");

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Password is required"),
  remember: z.boolean().optional(),
});

export const signupSchema = z
  .object({
    name: z.string().min(2, "Enter your full name"),
    email: emailSchema,
    password: strongPasswordSchema,
    confirmPassword: z.string().min(1, "Confirm your password"),
    terms: z.boolean().refine((v) => v === true, "Please accept the terms to continue"),
  })
  .refine((d) => d.password === d.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords do not match",
  });

export const forgotPasswordSchema = z.object({ email: emailSchema });

/** Choosing a new password from a reset link — same rules as signup. */
export const resetPasswordSchema = z
  .object({
    password: strongPasswordSchema,
    confirmPassword: z.string().min(1, "Confirm your password"),
  })
  .refine((d) => d.password === d.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords do not match",
  });

export const verifyEmailSchema = z.object({
  code: z
    .string()
    .min(1, "Enter the code")
    .regex(/^\d{6}$/, "Enter the 6-digit code"),
});

export type LoginValues = z.infer<typeof loginSchema>;
export type SignupValues = z.infer<typeof signupSchema>;
export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;
export type VerifyEmailValues = z.infer<typeof verifyEmailSchema>;
