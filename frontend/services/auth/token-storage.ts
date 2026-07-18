/**
 * Persistence for the backend session: the JWT pair plus a snapshot of the
 * authenticated user.
 *
 * Why a user snapshot? The backend exposes no `/auth/me` endpoint and
 * `POST /auth/login` returns tokens only, so the profile shown in the UI cannot
 * be re-fetched. We therefore cache what the backend has already told us
 * (at registration, or the previous session on this device) and rebuild the
 * user from the access-token claims when no snapshot exists.
 *
 * Leaf module: no imports, safe for both the HTTP client and the auth adapter.
 * All access is `try`/`catch`-guarded — Safari private mode and disabled storage
 * throw on `localStorage` access.
 */

import type { AuthUser } from "./types";

const TOKENS_KEY = "neuraevo.auth.tokens";
const USER_KEY = "neuraevo.auth.user";

export interface StoredTokens {
  accessToken: string;
  refreshToken: string;
}

interface AccessTokenClaims {
  sub?: string;
  exp?: number;
  type?: string;
}

function read<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function write(key: string, value: unknown | null): void {
  if (typeof window === "undefined") return;
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable — the session simply won't survive a reload */
  }
}

export function getTokens(): StoredTokens | null {
  const tokens = read<StoredTokens>(TOKENS_KEY);
  if (!tokens?.accessToken || !tokens?.refreshToken) return null;
  return tokens;
}

export function setTokens(tokens: StoredTokens): void {
  write(TOKENS_KEY, tokens);
}

export function getAccessToken(): string | null {
  return getTokens()?.accessToken ?? null;
}

export function getRefreshToken(): string | null {
  return getTokens()?.refreshToken ?? null;
}

export function getStoredUser(): AuthUser | null {
  return read<AuthUser>(USER_KEY);
}

export function setStoredUser(user: AuthUser | null): void {
  write(USER_KEY, user);
}

/** Drop every trace of the session. Used by logout and by refresh failure. */
export function clearSession(): void {
  write(TOKENS_KEY, null);
  write(USER_KEY, null);
}

/**
 * Decode a JWT payload without verifying it.
 *
 * The signature is verified by the backend on every request — this is only used
 * to read `sub`/`exp` for display and for the pre-emptive expiry check, never to
 * make an authorization decision.
 */
export function decodeAccessToken(token: string): AccessTokenClaims | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const json = atob(padded);
    // Recover non-ASCII characters that `atob` leaves as raw bytes.
    const decoded = decodeURIComponent(
      json
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join(""),
    );
    return JSON.parse(decoded) as AccessTokenClaims;
  } catch {
    return null;
  }
}

/** ISO expiry of an access token, or `null` when it carries no `exp`. */
export function accessTokenExpiry(token: string): string | null {
  const exp = decodeAccessToken(token)?.exp;
  return typeof exp === "number" ? new Date(exp * 1000).toISOString() : null;
}

/** `true` when the token is absent, unparseable, or past its `exp`. */
export function isAccessTokenExpired(token: string | null): boolean {
  if (!token) return true;
  const exp = decodeAccessToken(token)?.exp;
  if (typeof exp !== "number") return false; // no expiry claim — let the server decide
  return exp * 1000 <= Date.now();
}
