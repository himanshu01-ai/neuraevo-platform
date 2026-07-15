import {
  AuthError,
  type AuthAdapter,
  type AuthUser,
  type ForgotPasswordInput,
  type LoginInput,
  type Session,
  type SignupInput,
  type VerifyEmailInput,
} from "./types";

/**
 * Deterministic in-browser mock of an auth backend. No network, no real crypto.
 * A "session" is persisted to localStorage to simulate a server session so
 * refreshSession() survives reloads.
 *
 * Deterministic triggers (for demoing states):
 *  - login  → error@neuraevo.com OR password "wrongpassword" → invalid_credentials
 *  - signup → taken@neuraevo.com → email_exists
 *  - verify → code "000000" → invalid_code (any other 6 digits succeed)
 *  - forgotPassword → always { sent: true } (no user enumeration)
 */

const SESSION_KEY = "neuraevo.mock.session";
const LATENCY_MS = 650;

const delay = (ms = LATENCY_MS) => new Promise((r) => setTimeout(r, ms));

function hashId(email: string): string {
  let h = 0;
  for (let i = 0; i < email.length; i++) h = (h * 31 + email.charCodeAt(i)) | 0;
  return "usr_" + Math.abs(h).toString(36).padStart(6, "0");
}

function nameFromEmail(email: string): string {
  const local = email.split("@")[0] ?? "there";
  return local
    .split(/[._-]/)
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}

function readSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

function writeSession(session: Session | null) {
  if (typeof window === "undefined") return;
  try {
    if (session) window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    else window.localStorage.removeItem(SESSION_KEY);
  } catch {
    /* ignore */
  }
}

function makeSession(user: AuthUser): Session {
  return {
    user,
    token: "mock." + user.id + "." + Date.now().toString(36),
    expiresAt: new Date(Date.now() + 1000 * 60 * 60 * 24).toISOString(),
  };
}

export class MockAuthAdapter implements AuthAdapter {
  async login(input: LoginInput): Promise<Session> {
    await delay();
    if (input.email.toLowerCase() === "error@neuraevo.com" || input.password === "wrongpassword") {
      throw new AuthError("invalid_credentials", "That email or password is incorrect.");
    }
    const user: AuthUser = {
      id: hashId(input.email),
      email: input.email,
      name: nameFromEmail(input.email),
      emailVerified: true,
      createdAt: new Date().toISOString(),
    };
    const session = makeSession(user);
    writeSession(session);
    return session;
  }

  async signup(input: SignupInput): Promise<Session> {
    await delay();
    if (input.email.toLowerCase() === "taken@neuraevo.com") {
      throw new AuthError("email_exists", "An account with this email already exists.");
    }
    const user: AuthUser = {
      id: hashId(input.email),
      email: input.email,
      name: input.name,
      emailVerified: false,
      createdAt: new Date().toISOString(),
    };
    const session = makeSession(user);
    writeSession(session);
    return session;
  }

  async logout(): Promise<void> {
    await delay(250);
    writeSession(null);
  }

  async forgotPassword(_input: ForgotPasswordInput): Promise<{ sent: true }> {
    await delay();
    return { sent: true };
  }

  async verifyEmail(input: VerifyEmailInput): Promise<AuthUser> {
    await delay();
    if (input.code === "000000") {
      throw new AuthError("invalid_code", "That code is invalid or expired.");
    }
    const existing = readSession();
    const user: AuthUser = existing
      ? { ...existing.user, emailVerified: true }
      : {
          id: hashId(input.email),
          email: input.email,
          name: nameFromEmail(input.email),
          emailVerified: true,
          createdAt: new Date().toISOString(),
        };
    writeSession(makeSession(user));
    return user;
  }

  async refreshSession(): Promise<Session | null> {
    await delay(300);
    return readSession();
  }

  async currentUser(): Promise<AuthUser | null> {
    await delay(150);
    return readSession()?.user ?? null;
  }
}
