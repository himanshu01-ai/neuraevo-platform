/**
 * Auth domain contracts — provider-independent. The app depends only on these
 * types and the `AuthAdapter` interface, never on a concrete provider. Sprint
 * 17.2 ships a deterministic mock adapter; a real backend adapter can be dropped
 * in later with zero changes to callers.
 */

export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
  emailVerified: boolean;
  createdAt: string;
}

export interface Session {
  user: AuthUser;
  token: string;
  expiresAt: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface SignupInput {
  name: string;
  email: string;
  password: string;
}

export interface ForgotPasswordInput {
  email: string;
}

export interface VerifyEmailInput {
  email: string;
  code: string;
}

export type AuthErrorCode =
  | "invalid_credentials"
  | "email_exists"
  | "invalid_code"
  | "not_found"
  | "unknown";

export class AuthError extends Error {
  code: AuthErrorCode;
  constructor(code: AuthErrorCode, message: string) {
    super(message);
    this.name = "AuthError";
    this.code = code;
  }
}

/** The single seam every auth backend must implement. */
export interface AuthAdapter {
  login(input: LoginInput): Promise<Session>;
  signup(input: SignupInput): Promise<Session>;
  logout(): Promise<void>;
  forgotPassword(input: ForgotPasswordInput): Promise<{ sent: true }>;
  verifyEmail(input: VerifyEmailInput): Promise<AuthUser>;
  refreshSession(): Promise<Session | null>;
  currentUser(): Promise<AuthUser | null>;
}
