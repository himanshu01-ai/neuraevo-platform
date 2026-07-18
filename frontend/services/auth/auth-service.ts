import { env } from "@/lib/env";
import { BackendAuthAdapter } from "./backend-adapter";
import { MockAuthAdapter } from "./mock-adapter";
import type {
  AuthAdapter,
  AuthCapabilities,
  ForgotPasswordInput,
  LoginInput,
  SignupInput,
  VerifyEmailInput,
} from "./types";

/**
 * The app's single entry point to auth, and the only place that knows which
 * adapter is active. Callers (hooks, guards, forms) never import an adapter.
 *
 * Sprint 18.1 swapped the default from the Sprint 17 mock to the real FastAPI
 * backend. The mock remains selectable via `NEXT_PUBLIC_AUTH_ADAPTER=mock` for
 * offline UI work; the choice is app-wide, so mock and real flows are never
 * mixed within a session.
 */
const adapter: AuthAdapter =
  env.NEXT_PUBLIC_AUTH_ADAPTER === "mock" ? new MockAuthAdapter() : new BackendAuthAdapter();

export const authService = {
  /**
   * Operations the active backend genuinely supports. The UI gates entry points
   * on this instead of offering an action that cannot succeed.
   */
  capabilities: adapter.capabilities as Readonly<AuthCapabilities>,
  login: (input: LoginInput) => adapter.login(input),
  signup: (input: SignupInput) => adapter.signup(input),
  logout: () => adapter.logout(),
  forgotPassword: (input: ForgotPasswordInput) => adapter.forgotPassword(input),
  verifyEmail: (input: VerifyEmailInput) => adapter.verifyEmail(input),
  refreshSession: () => adapter.refreshSession(),
  currentUser: () => adapter.currentUser(),
};

export type AuthService = typeof authService;
