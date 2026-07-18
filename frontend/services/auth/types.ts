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
  | "network_error"
  | "validation_error"
  | "feature_unavailable"
  | "unknown";

export class AuthError extends Error {
  code: AuthErrorCode;
  constructor(code: AuthErrorCode, message: string) {
    super(message);
    this.name = "AuthError";
    this.code = code;
  }
}

/**
 * Raised when an operation exists on the adapter interface but the active
 * backend does not implement it. The adapter never fakes a success — callers
 * should gate the entry point on `capabilities` so this is a guard, not a
 * routine path.
 */
export class AuthFeatureUnavailableError extends AuthError {
  feature: AuthFeature;
  constructor(feature: AuthFeature, message: string) {
    super("feature_unavailable", message);
    this.name = "AuthFeatureUnavailableError";
    this.feature = feature;
  }
}

export type AuthFeature = "forgotPassword" | "verifyEmail";

/**
 * Which optional operations the active backend actually supports. The UI reads
 * this to hide or disable entry points rather than offering an action that
 * cannot succeed.
 */
export type AuthCapabilities = Record<AuthFeature, boolean>;

/** The single seam every auth backend must implement. */
export interface AuthAdapter {
  /** Operations this adapter can genuinely fulfil against its backend. */
  readonly capabilities: AuthCapabilities;
  login(input: LoginInput): Promise<Session>;
  signup(input: SignupInput): Promise<Session>;
  logout(): Promise<void>;
  forgotPassword(input: ForgotPasswordInput): Promise<{ sent: true }>;
  verifyEmail(input: VerifyEmailInput): Promise<AuthUser>;
  refreshSession(): Promise<Session | null>;
  currentUser(): Promise<AuthUser | null>;
}
