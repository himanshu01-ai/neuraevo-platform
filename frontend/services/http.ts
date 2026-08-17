/**
 * The app's single HTTP client (see docs/09-state-and-api.md).
 *
 * Owns the base URL, JSON handling, the `Authorization` interceptor, automatic
 * access-token refresh with a one-shot 401 retry, and normalization of every
 * failure to one `ApiError` shape. No raw `fetch` is permitted anywhere else.
 *
 * Refresh is single-flight: concurrent 401s share one `POST /auth/refresh`
 * instead of each firing their own. If refresh fails, the session is cleared and
 * subscribers are notified once so the app can reset state and redirect.
 */

import { apiBaseUrl } from "@/lib/env";
import { clearSession, getAccessToken, getRefreshToken, setTokens } from "./auth/token-storage";

export interface ApiErrorShape {
  status: number;
  code: string;
  message: string;
  details?: unknown;
}

/** The one error shape every UI error state reads. */
export class ApiError extends Error implements ApiErrorShape {
  status: number;
  code: string;
  details?: unknown;

  constructor({ status, code, message, details }: ApiErrorShape) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** No response reached us (offline, DNS, CORS preflight, aborted connection). */
  get isNetworkError(): boolean {
    return this.status === 0;
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  /** Attach the bearer token and enable refresh-on-401. Default `true`. */
  auth?: boolean;
  /** Internal: suppresses the refresh/retry cycle (used by refresh itself). */
  skipRefresh?: boolean;
  /**
   * Per-request timeout in milliseconds. Defaults to
   * {@link DEFAULT_REQUEST_TIMEOUT_MS}; pass `0` to disable for a call that is
   * legitimately long-running.
   */
  timeoutMs?: number;
}

/**
 * Requests that don't resolve within this budget are aborted, so a hung or
 * black-holed backend surfaces as a clear error instead of an endless spinner.
 * Deliberately generous — comfortably longer than the backend's own upstream
 * timeouts (e.g. the 30s Anthropic cap) so a legitimately slow response, such as
 * an AI generation, is never cut off.
 */
export const DEFAULT_REQUEST_TIMEOUT_MS = 60_000;

// --- Session-expiry subscribers -----------------------------------------

type LogoutListener = () => void;
const logoutListeners = new Set<LogoutListener>();

/**
 * Subscribe to forced logout (refresh failed / refresh token rejected).
 * Returns an unsubscribe function — callers must call it on unmount so the
 * listener set never leaks.
 */
export function onSessionExpired(listener: LogoutListener): () => void {
  logoutListeners.add(listener);
  return () => logoutListeners.delete(listener);
}

function notifySessionExpired(): void {
  clearSession();
  for (const listener of logoutListeners) {
    try {
      listener();
    } catch {
      /* one bad subscriber must not block the others */
    }
  }
}

// --- Error normalization -------------------------------------------------

/**
 * Turn a FastAPI `detail` into a readable sentence.
 *
 * `detail` is a plain string for our handled errors and a list of
 * `{loc, msg, type}` objects for 422 validation failures.
 */
function messageFromDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          const { msg, loc } = item as { msg?: unknown; loc?: unknown };
          if (typeof msg !== "string") return null;
          // Drop the leading "body" segment so the field name reads naturally.
          const field = Array.isArray(loc) ? loc.filter((p) => p !== "body").join(".") : "";
          return field ? `${field}: ${msg}` : msg;
        }
        return null;
      })
      .filter((m): m is string => Boolean(m));

    if (messages.length) return messages.join(" ");
  }

  return fallback;
}

const STATUS_CODES: Record<number, string> = {
  400: "bad_request",
  401: "unauthorized",
  403: "forbidden",
  404: "not_found",
  409: "conflict",
  422: "validation_error",
  429: "rate_limited",
};

function codeForStatus(status: number): string {
  return STATUS_CODES[status] ?? (status >= 500 ? "server_error" : "http_error");
}

const DEFAULT_MESSAGES: Record<number, string> = {
  401: "Your session is no longer valid.",
  403: "You don't have access to this resource.",
  404: "We couldn't find what you were looking for.",
  409: "That conflicts with something that already exists.",
  422: "Some of the submitted values are invalid.",
  429: "Too many requests. Please wait a moment and try again.",
};

async function errorFromResponse(response: Response): Promise<ApiError> {
  let detail: unknown;
  try {
    const body = await response.json();
    detail = body && typeof body === "object" && "detail" in body ? body.detail : body;
  } catch {
    /* empty or non-JSON error body */
  }

  const fallback =
    DEFAULT_MESSAGES[response.status] ??
    (response.status >= 500
      ? "The server ran into a problem. Please try again."
      : "Something went wrong. Please try again.");

  return new ApiError({
    status: response.status,
    code: codeForStatus(response.status),
    message: messageFromDetail(detail, fallback),
    details: detail,
  });
}

// --- Token refresh (single-flight) --------------------------------------

let refreshInFlight: Promise<string | null> | null = null;

/** Exchange the refresh token for a new pair. Returns the new access token. */
async function performRefresh(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const tokens = await request<{ access_token: string; refresh_token: string }>(
      "/auth/refresh",
      { method: "POST", body: { refresh_token: refreshToken }, auth: false, skipRefresh: true },
    );
    setTokens({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
    return tokens.access_token;
  } catch {
    // Covers both a rejected refresh token (401) and transport failure. Either
    // way we cannot prove the session is still valid.
    return null;
  }
}

/**
 * Refresh the access token, coalescing concurrent callers onto one request.
 * Exposed so the auth adapter can drive session restore through the same path.
 */
export function refreshAccessToken(): Promise<string | null> {
  refreshInFlight ??= performRefresh().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

// --- Core request --------------------------------------------------------

async function send(path: string, options: RequestOptions, token: string | null): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  // Bound every request with a timeout while still honoring a caller-supplied
  // signal (e.g. a cancelled query). A dedicated controller lets us tell a
  // timeout apart from a genuine caller cancellation when reporting the error.
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS;
  const timer = timeoutMs > 0 ? setTimeout(() => controller.abort(), timeoutMs) : undefined;
  const onCallerAbort = () => controller.abort();
  if (options.signal) {
    if (options.signal.aborted) controller.abort();
    else options.signal.addEventListener("abort", onCallerAbort, { once: true });
  }

  try {
    return await fetch(`${apiBaseUrl}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });
  } catch (cause) {
    // A genuine caller cancellation propagates as AbortError, unchanged, so
    // React Query and unmount handling keep working. A timeout (the caller did
    // not cancel) becomes a readable, network-style error instead.
    if (options.signal?.aborted) throw cause;
    if (controller.signal.aborted) {
      throw new ApiError({
        status: 0,
        code: "timeout",
        message: "The server took too long to respond. Please try again.",
        details: cause,
      });
    }
    throw new ApiError({
      status: 0,
      code: "network_error",
      message: "We couldn't reach the server. Check your connection and try again.",
      details: cause,
    });
  } finally {
    if (timer) clearTimeout(timer);
    options.signal?.removeEventListener("abort", onCallerAbort);
  }
}

async function parse<T>(response: Response): Promise<T> {
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError({
      status: response.status,
      code: "invalid_response",
      message: "The server returned a response we couldn't read.",
    });
  }
}

/**
 * Perform a request against the API.
 *
 * On a 401 with authentication enabled, refreshes the access token once and
 * replays the request. If refresh fails, the session is cleared, subscribers are
 * notified, and the original 401 surfaces to the caller.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const useAuth = options.auth !== false;
  const response = await send(path, options, useAuth ? getAccessToken() : null);

  if (response.ok) return parse<T>(response);

  if (response.status === 401 && useAuth && !options.skipRefresh) {
    const newToken = await refreshAccessToken();
    if (!newToken) {
      notifySessionExpired();
      throw await errorFromResponse(response);
    }

    const retried = await send(path, options, newToken);
    if (retried.ok) return parse<T>(retried);
    // Still unauthorized with a token the server just issued — the session is
    // genuinely finished, so stop retrying.
    if (retried.status === 401) notifySessionExpired();
    throw await errorFromResponse(retried);
  }

  throw await errorFromResponse(response);
}
