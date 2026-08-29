export const API_ROOT = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001/api/v1";

export type AuthUser = {
  id: string;
  name: string;
  email: string;
  is_verified: boolean;
  created_at: string;
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

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      ...init,
      cache: "no-store",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch {
    throw new ApiError(
      "The authentication server is unavailable. Start the FastAPI backend and try again.",
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

export function registerAccount(input: { name: string; email: string; password: string }) {
  return apiRequest<AuthSession>("/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
  }).then(validateAuthSession);
}

export function loginAccount(input: { email: string; password: string }) {
  return apiRequest<AuthSession>("/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  }).then(validateAuthSession);
}

let refreshPromise: Promise<AuthSession | null> | null = null;

async function requestRestoredSession(): Promise<AuthSession | null> {
  return apiRequest<AuthSession>("/auth/refresh", { method: "POST" })
    .then(validateAuthSession)
    .catch((error: unknown) => {
      if (error instanceof ApiError && error.status === 401) return null;
      throw error;
    });
}

async function restoreWithCrossTabLock(): Promise<AuthSession | null> {
  if (typeof navigator !== "undefined" && navigator.locks) {
    return await navigator.locks.request("abhyaas-session-refresh", requestRestoredSession);
  }
  return requestRestoredSession();
}

export function restoreAuthSession(): Promise<AuthSession | null> {
  if (!refreshPromise) {
    refreshPromise = restoreWithCrossTabLock()
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export function logoutAccount() {
  return apiRequest<MessageResponse>("/auth/logout", { method: "POST" });
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
  if (!session?.access_token || !session.user?.id || !session.user?.email) {
    throw new ApiError("The authentication server returned an invalid session.", 502);
  }
  return session;
}
