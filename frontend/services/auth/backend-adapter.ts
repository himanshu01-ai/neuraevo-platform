import { z } from "zod";
import { ApiError, request } from "../http";
import {
  accessTokenExpiry,
  clearSession,
  getAccessToken,
  getTokens,
  setTokens,
} from "./token-storage";
import {
  AuthError,
  type AuthAdapter,
  type AuthUser,
  type ForgotPasswordInput,
  type LoginInput,
  type ResendVerificationInput,
  type Session,
  type SignupInput,
  type VerifyEmailInput,
} from "./types";

/**
 * Real auth adapter, backed by the FastAPI service. Implements the same
 * `AuthAdapter` seam as the mock, so no caller changes.
 *
 * Sprint 18.1A completed the backend, so this adapter no longer derives
 * anything it cannot read:
 *
 *   POST /auth/register            -> 201 UserResponse
 *   POST /auth/login               -> 200 TokenResponse
 *   POST /auth/refresh             -> 200 TokenResponse
 *   GET  /auth/me                  -> 200 UserResponse   (authoritative profile)
 *   POST /auth/logout              -> 204                (revokes issued tokens)
 *   POST /auth/forgot-password     -> 202 MessageResponse
 *   POST /auth/verify-email        -> 200 UserResponse
 *   POST /auth/resend-verification -> 202 MessageResponse
 *
 * The profile always comes from `GET /auth/me` — never from JWT claims, the
 * submitted email, or a cached snapshot. Token refresh stays in `http.ts`, so
 * an expired access token is renewed transparently underneath these calls.
 */

// --- Backend wire schemas ------------------------------------------------
// Mirrors of the Pydantic models in backend/app/schemas/auth.py, validated at
// the boundary and mapped straight into the domain types below.

const tokenResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  token_type: z.string().default("bearer"),
});

const userResponseSchema = z.object({
  id: z.string(),
  email: z.string(),
  full_name: z.string().nullable().optional(),
  avatar_url: z.string().nullable().optional(),
  is_active: z.boolean(),
  email_verified: z.boolean(),
  email_verified_at: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

type UserResponse = z.infer<typeof userResponseSchema>;

// --- Mapping -------------------------------------------------------------

function toAuthUser(user: UserResponse): AuthUser {
  return {
    id: user.id,
    email: user.email,
    name: user.full_name ?? null,
    avatarUrl: user.avatar_url ?? null,
    emailVerified: user.email_verified,
    createdAt: user.created_at,
  };
}

function parseOrThrow<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    throw new AuthError("unknown", "The server returned an unexpected response.");
  }
  return result.data;
}

/** Map a transport-level `ApiError` onto the auth domain's error vocabulary. */
function toAuthError(error: unknown, fallback: string): AuthError {
  if (error instanceof AuthError) return error;

  if (error instanceof ApiError) {
    if (error.isNetworkError) return new AuthError("network_error", error.message);
    if (error.status === 429) return new AuthError("rate_limited", error.message);
    if (error.status === 401) return new AuthError("invalid_credentials", error.message);
    if (error.status === 409) return new AuthError("email_exists", error.message);
    if (error.status === 400) return new AuthError("invalid_code", error.message);
    if (error.status === 422) return new AuthError("validation_error", error.message);
    if (error.status === 404) return new AuthError("not_found", error.message);
    return new AuthError("unknown", error.message);
  }

  return new AuthError("unknown", fallback);
}

function sessionFor(user: AuthUser, accessToken: string): Session {
  return {
    user,
    token: accessToken,
    expiresAt: accessTokenExpiry(accessToken) ?? new Date().toISOString(),
  };
}

// --- Adapter -------------------------------------------------------------

export class BackendAuthAdapter implements AuthAdapter {
  /** Exchange credentials for tokens and persist them. */
  private async authenticate(email: string, password: string): Promise<string> {
    const raw = await request<unknown>("/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    });
    const tokens = parseOrThrow(tokenResponseSchema, raw);
    setTokens({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
    });
    return tokens.access_token;
  }

  /** The authenticated user, straight from the database. */
  private async fetchMe(): Promise<AuthUser> {
    const raw = await request<unknown>("/auth/me");
    return toAuthUser(parseOrThrow(userResponseSchema, raw));
  }

  async login(input: LoginInput): Promise<Session> {
    try {
      const accessToken = await this.authenticate(input.email, input.password);
      return sessionFor(await this.fetchMe(), accessToken);
    } catch (error) {
      throw toAuthError(error, "Unable to sign in.");
    }
  }

  /**
   * Register, then immediately log in.
   *
   * `POST /auth/register` returns the created user but no tokens, so a second
   * call is required to obtain a session. Both run inside one adapter call, so
   * the UI still sees a single "sign up" operation. Registration also triggers
   * the verification email on the backend.
   */
  async signup(input: SignupInput): Promise<Session> {
    let created: AuthUser;
    try {
      const raw = await request<unknown>("/auth/register", {
        method: "POST",
        body: { email: input.email, password: input.password, full_name: input.name },
        auth: false,
      });
      created = toAuthUser(parseOrThrow(userResponseSchema, raw));
    } catch (error) {
      throw toAuthError(error, "Unable to create your account.");
    }

    try {
      const accessToken = await this.authenticate(input.email, input.password);
      return sessionFor(created, accessToken);
    } catch {
      // The account now exists but we hold no session. Surface it plainly so
      // the user signs in rather than re-registering into a 409.
      throw new AuthError(
        "unknown",
        "Your account was created, but we couldn't sign you in. Please sign in.",
      );
    }
  }

  /**
   * Revoke the session server-side, then clear it locally.
   *
   * Local tokens are cleared even if the call fails — an already-expired or
   * already-revoked token still means the user is logged out here.
   */
  async logout(): Promise<void> {
    try {
      if (getAccessToken()) {
        await request<void>("/auth/logout", { method: "POST", body: {} });
      }
    } catch {
      /* best effort — clearing local tokens below is what matters */
    } finally {
      clearSession();
    }
  }

  async forgotPassword(input: ForgotPasswordInput): Promise<{ sent: true }> {
    try {
      await request<unknown>("/auth/forgot-password", {
        method: "POST",
        body: { email: input.email },
        auth: false,
      });
      return { sent: true };
    } catch (error) {
      throw toAuthError(error, "Unable to send the reset email.");
    }
  }

  async verifyEmail(input: VerifyEmailInput): Promise<AuthUser> {
    try {
      const raw = await request<unknown>("/auth/verify-email", {
        method: "POST",
        body: { email: input.email, code: input.code },
        auth: false,
      });
      return toAuthUser(parseOrThrow(userResponseSchema, raw));
    } catch (error) {
      throw toAuthError(error, "That code is invalid or expired.");
    }
  }

  async resendVerification(
    input: ResendVerificationInput,
  ): Promise<{ sent: true }> {
    try {
      await request<unknown>("/auth/resend-verification", {
        method: "POST",
        body: { email: input.email },
        auth: false,
      });
      return { sent: true };
    } catch (error) {
      throw toAuthError(error, "Unable to resend the code.");
    }
  }

  /**
   * Restore the session on boot or reload.
   *
   * Asks the backend who the caller is; `http.ts` transparently refreshes an
   * expired access token and clears the session if that fails, so a `null`
   * here means "not signed in" and the guards can act on it directly.
   */
  async refreshSession(): Promise<Session | null> {
    const tokens = getTokens();
    if (!tokens) return null;

    try {
      const user = await this.fetchMe();
      return sessionFor(user, getAccessToken() ?? tokens.accessToken);
    } catch {
      clearSession();
      return null;
    }
  }

  async currentUser(): Promise<AuthUser | null> {
    if (!getAccessToken()) return null;
    try {
      return await this.fetchMe();
    } catch {
      return null;
    }
  }
}
