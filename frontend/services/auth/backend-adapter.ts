import { z } from "zod";
import { ApiError, refreshAccessToken, request } from "../http";
import {
  accessTokenExpiry,
  clearSession,
  decodeAccessToken,
  getAccessToken,
  getStoredUser,
  getTokens,
  isAccessTokenExpired,
  setStoredUser,
  setTokens,
} from "./token-storage";
import {
  AuthError,
  AuthFeatureUnavailableError,
  type AuthAdapter,
  type AuthCapabilities,
  type AuthUser,
  type ForgotPasswordInput,
  type LoginInput,
  type Session,
  type SignupInput,
  type VerifyEmailInput,
} from "./types";

/**
 * Real auth adapter, backed by the FastAPI service. Implements the same
 * `AuthAdapter` seam as the Sprint 17 mock, so no caller changes.
 *
 * The backend (backend/app/api/v1/auth.py) implements exactly three endpoints:
 *
 *   POST /auth/register  -> 201 UserResponse   (no tokens)
 *   POST /auth/login     -> 200 TokenResponse  (no user)
 *   POST /auth/refresh   -> 200 TokenResponse
 *
 * Everything else in the interface is derived from those, or reported as
 * unavailable. Nothing is simulated.
 *
 * Consequences of that contract, handled here:
 *  - `signup` composes register + login, because register issues no tokens.
 *  - `logout` is client-side only; JWTs are stateless and there is no denylist
 *    endpoint to call.
 *  - `currentUser` reads the cached profile and the access-token claims, because
 *    no `/auth/me` endpoint exists.
 *  - `forgotPassword` / `verifyEmail` have no backend at all and therefore
 *    reject with `AuthFeatureUnavailableError`.
 */

// --- Backend wire schemas ------------------------------------------------
// Mirrors of the Pydantic models in backend/app/schemas/auth.py, validated at
// the boundary. These are the backend's models, not a parallel set of DTOs —
// they are mapped straight into the domain types below.

const tokenResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  token_type: z.string().default("bearer"),
});

const userResponseSchema = z.object({
  id: z.string(),
  email: z.string(),
  full_name: z.string().nullable().optional(),
  is_active: z.boolean(),
  created_at: z.string(),
});

type UserResponse = z.infer<typeof userResponseSchema>;

// --- Mapping -------------------------------------------------------------

/**
 * The backend `User` model has no email-verification concept (only
 * `is_active`), so every backend-issued user is treated as verified. Mapping
 * `is_active` onto `emailVerified` would conflate two unrelated states.
 */
function toAuthUser(user: UserResponse): AuthUser {
  return {
    id: user.id,
    email: user.email,
    name: user.full_name ?? null,
    emailVerified: true,
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
    if (error.status === 401) return new AuthError("invalid_credentials", error.message);
    if (error.status === 409) return new AuthError("email_exists", error.message);
    if (error.status === 422) return new AuthError("validation_error", error.message);
    if (error.status === 404) return new AuthError("not_found", error.message);
    return new AuthError("unknown", error.message);
  }

  return new AuthError("unknown", fallback);
}

// --- Session assembly ----------------------------------------------------

/**
 * Build the domain `Session` from a freshly issued token pair, persisting both
 * the tokens and the best user profile we can assemble.
 *
 * `profile` is supplied when the backend has just told us who the user is (only
 * registration does). Otherwise we fall back to the cached profile for the same
 * user id, then to the token's `sub` claim plus the email the caller signed in
 * with — the backend offers no way to read the profile back.
 */
function establishSession(
  accessToken: string,
  refreshToken: string,
  profile: AuthUser | null,
  knownEmail?: string,
): Session {
  setTokens({ accessToken, refreshToken });

  const claims = decodeAccessToken(accessToken);
  const userId = claims?.sub ?? profile?.id ?? "";
  const cached = getStoredUser();
  const cachedForThisUser = cached && cached.id === userId ? cached : null;

  const user: AuthUser = profile ?? {
    id: userId,
    email: knownEmail ?? cachedForThisUser?.email ?? "",
    name: cachedForThisUser?.name ?? null,
    emailVerified: true,
    createdAt: cachedForThisUser?.createdAt ?? new Date().toISOString(),
  };

  setStoredUser(user);

  return {
    user,
    token: accessToken,
    expiresAt: accessTokenExpiry(accessToken) ?? new Date().toISOString(),
  };
}

// --- Adapter -------------------------------------------------------------

export class BackendAuthAdapter implements AuthAdapter {
  /** The FastAPI backend implements neither of these; see the class docblock. */
  readonly capabilities: AuthCapabilities = {
    forgotPassword: false,
    verifyEmail: false,
  };

  async login(input: LoginInput): Promise<Session> {
    try {
      const raw = await request<unknown>("/auth/login", {
        method: "POST",
        body: { email: input.email, password: input.password },
        auth: false,
      });
      const tokens = parseOrThrow(tokenResponseSchema, raw);
      return establishSession(tokens.access_token, tokens.refresh_token, null, input.email);
    } catch (error) {
      throw toAuthError(error, "Unable to sign in.");
    }
  }

  /**
   * Register, then immediately log in.
   *
   * `POST /auth/register` returns the created user but no tokens, so a second
   * call is required to obtain a session. Both run inside one adapter call, so
   * the UI still sees a single "sign up" operation.
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
      const raw = await request<unknown>("/auth/login", {
        method: "POST",
        body: { email: input.email, password: input.password },
        auth: false,
      });
      const tokens = parseOrThrow(tokenResponseSchema, raw);
      return establishSession(tokens.access_token, tokens.refresh_token, created);
    } catch (error) {
      // The account now exists but we hold no session. Surface it plainly rather
      // than as a signup failure, so the user signs in instead of re-registering
      // into a 409.
      const authError = toAuthError(error, "Your account was created, but sign-in failed.");
      throw new AuthError(
        authError.code === "invalid_credentials" ? "unknown" : authError.code,
        "Your account was created, but we couldn't sign you in. Please sign in.",
      );
    }
  }

  /**
   * Client-side only. The backend issues stateless JWTs and exposes no logout or
   * token-revocation endpoint, so the tokens are simply discarded; they remain
   * technically valid until they expire.
   */
  async logout(): Promise<void> {
    clearSession();
  }

  async forgotPassword(_input: ForgotPasswordInput): Promise<{ sent: true }> {
    throw new AuthFeatureUnavailableError(
      "forgotPassword",
      "Password reset isn't available yet. Contact your administrator to regain access.",
    );
  }

  async verifyEmail(_input: VerifyEmailInput): Promise<AuthUser> {
    throw new AuthFeatureUnavailableError(
      "verifyEmail",
      "Email verification isn't available yet. Your account is already active.",
    );
  }

  /**
   * Restore the session on boot or reload.
   *
   * A live access token is used as-is; an expired one is exchanged through the
   * shared single-flight refresh in `http.ts`. When no refresh is possible the
   * session is cleared and `null` is returned, which the guards read as
   * unauthenticated.
   */
  async refreshSession(): Promise<Session | null> {
    const tokens = getTokens();
    if (!tokens) return null;

    if (!isAccessTokenExpired(tokens.accessToken)) {
      const stored = getStoredUser();
      if (stored) {
        return {
          user: stored,
          token: tokens.accessToken,
          expiresAt: accessTokenExpiry(tokens.accessToken) ?? new Date().toISOString(),
        };
      }
    }

    const accessToken = await refreshAccessToken();
    if (!accessToken) {
      clearSession();
      return null;
    }

    const refreshed = getTokens();
    if (!refreshed) return null;
    return establishSession(accessToken, refreshed.refreshToken, getStoredUser());
  }

  /**
   * The cached profile for the current token.
   *
   * There is no `/auth/me` endpoint to read the profile back, so this reports
   * what we hold locally and never issues a request. A token that has been
   * revoked server-side surfaces on the next real API call as a 401, which the
   * HTTP client turns into a refresh attempt and, failing that, a logout.
   */
  async currentUser(): Promise<AuthUser | null> {
    const token = getAccessToken();
    if (!token) return null;
    if (isAccessTokenExpired(token)) {
      const session = await this.refreshSession();
      return session?.user ?? null;
    }
    return getStoredUser();
  }
}
