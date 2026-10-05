import type { AcademyTarget } from "./academy-preference";
import { createSessionController } from "./session-controller";

export const API_ROOT = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001/api/v1";

export type AuthUser = {
  id: string;
  name: string;
  email: string;
  is_verified: boolean;
  created_at: string;
  target_academy: AcademyTarget | null;
};

export type AuthSession = {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: AuthUser;
};

type MessageResponse = { message: string };

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function rawApiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      ...init,
      cache: "no-store",
      credentials: "include",
      headers: new Headers({ "Content-Type": "application/json", ...Object.fromEntries(new Headers(init.headers)) }),
    });
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new ApiError(
      "Couldn't connect to Abhyaas. Check your connection and try again.",
      0,
    );
  }

  const payload = (await response.json().catch(() => ({}))) as {
    detail?: string | Array<{ msg?: string }>;
  } & T;

  if (!response.ok) {
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((item) => item.msg).filter(Boolean).join(". ")
      : payload.detail;
    throw new ApiError(detail || "The request could not be completed.", response.status);
  }
  return payload;
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = headers.get("Authorization")?.replace(/^Bearer /i, "");
  if (!token || path.startsWith("/auth/") || !sessionController.ownsToken(token)) {
    return rawApiRequest<T>(path, init);
  }
  const generation = sessionController.getGeneration();
  const withCurrentToken = () => {
    init.signal?.throwIfAborted();
    const session = sessionController.getSnapshot().session;
    if (!session || generation !== sessionController.getGeneration()) {
      throw new ApiError("Your session has changed. Please try again.", 401);
    }
    headers.set("Authorization", `Bearer ${session.access_token}`);
    return { ...init, headers };
  };
  const session = sessionController.getSnapshot().session;
  if (session && Date.parse(session.expires_at) <= Date.now() + 5_000) {
    await restoreAuthSession();
  }
  try {
    return await rawApiRequest<T>(path, withCurrentToken());
  } catch (error) {
    // Only an explicit auth rejection is safe to replay, never an ambiguous
    // network/5xx failure (a write might already have reached the server).
    if (!(error instanceof ApiError) || error.status !== 401
      || generation !== sessionController.getGeneration()) throw error;
    init.signal?.throwIfAborted();
    await restoreAuthSession();
    return rawApiRequest<T>(path, withCurrentToken());
  }
}

export function registerAccount(input: { name: string; email: string; password: string }) {
  return withAuthCookieLock(() => rawApiRequest<AuthSession>("/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
  }).then(validateAuthSession));
}

export function loginAccount(input: { email: string; password: string }) {
  return withAuthCookieLock(() => rawApiRequest<AuthSession>("/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  }).then(validateAuthSession));
}

export const sessionController = createSessionController(
  () => withAuthCookieLock(requestRestoredSession),
);

async function requestRestoredSession(): Promise<AuthSession | null> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      return validateAuthSession(
        await rawApiRequest<AuthSession>("/auth/refresh", { method: "POST", signal: AbortSignal.timeout(15_000) }),
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return null;
      const transientFailure = (error instanceof ApiError
        && (error.status === 0 || error.status >= 500))
        || (error instanceof Error && error.name === "TimeoutError");
      if (!transientFailure || attempt === 1) throw error;
      await new Promise((resolve) => setTimeout(resolve, 700));
    }
  }
  return null;
}

async function withAuthCookieLock<T>(operation: () => Promise<T>): Promise<T> {
  if (typeof navigator !== "undefined" && navigator.locks) {
    return await navigator.locks.request("abhyaas-session-refresh", operation);
  }
  return operation();
}

export function restoreAuthSession(): Promise<AuthSession | null> {
  return sessionController.refresh();
}

export function logoutAccount() {
  return withAuthCookieLock(async () => {
    const response = await rawApiRequest<MessageResponse>("/auth/logout", {
      method: "POST", signal: AbortSignal.timeout(15_000),
    });
    sessionController.endSession();
    return response;
  });
}

export function saveAcademyPreference(accessToken: string, target: AcademyTarget | null) {
  return apiRequest<AuthUser>("/users/me/preferences", {
    method: "PATCH",
    headers: { Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ target_academy: target }),
  });
}

export function getGoogleSignInUrl() {
  return `${API_ROOT}/auth/google/start`;
}

export function verifyEmail(token: string) {
  return apiRequest<MessageResponse>("/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function requestPasswordReset(email: string) {
  return apiRequest<MessageResponse>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(token: string, password: string) {
  return apiRequest<MessageResponse>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
}

function validateAuthSession(session: AuthSession): AuthSession {
  if (!session?.access_token || !session.user?.id || !session.user?.email
    || !Number.isFinite(Date.parse(session.expires_at))) {
    throw new ApiError("The authentication server returned an invalid session.", 502);
  }
  return session;
}
