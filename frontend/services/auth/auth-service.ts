import { MockAuthAdapter } from "./mock-adapter";
import type {
  AuthAdapter,
  ForgotPasswordInput,
  LoginInput,
  SignupInput,
  VerifyEmailInput,
} from "./types";

/**
 * The app's single entry point to auth. Swapping providers = swapping this one
 * adapter; callers (hooks, guards, forms) never change. No fetch/axios/SDKs.
 */
const adapter: AuthAdapter = new MockAuthAdapter();

export const authService = {
  login: (input: LoginInput) => adapter.login(input),
  signup: (input: SignupInput) => adapter.signup(input),
  logout: () => adapter.logout(),
  forgotPassword: (input: ForgotPasswordInput) => adapter.forgotPassword(input),
  verifyEmail: (input: VerifyEmailInput) => adapter.verifyEmail(input),
  refreshSession: () => adapter.refreshSession(),
  currentUser: () => adapter.currentUser(),
};

export type AuthService = typeof authService;
