import type { AuthStatus } from "./session-controller";

const publicPaths = new Set(["/", "/login", "/about", "/privacy", "/auth/callback"]);

// Home is always the public landing page. Never gate it on a session request or
// read window.location during rendering (it can lag behind a client transition).
export function authRedirect(pathname: string, status: AuthStatus): string | null {
  if (status === "loading") return null;
  if (status === "authenticated" && pathname === "/login") {
    return "/progress";
  }
  if (status === "anonymous" && !publicPaths.has(pathname)) {
    return `/login?next=${encodeURIComponent(pathname)}`;
  }
  return null;
}

// Do not briefly render the login form while a returning session is restored.
// This must not block the public landing page or other public routes.
export function shouldWaitForSession(pathname: string, status: AuthStatus): boolean {
  return pathname === "/login" && status === "loading";
}

export function shouldShowSessionRecovery(pathname: string, status: AuthStatus): boolean {
  return status === "unavailable"
    && (!publicPaths.has(pathname) || pathname === "/login" || pathname === "/auth/callback");
}

// The callback owns its redirect; the provider must not race it back to Login.
export function googleCallbackRedirect(status: AuthStatus, error: string | null): string | null {
  if (error) return `/login?google_error=${encodeURIComponent(error)}`;
  if (status === "loading" || status === "unavailable") return null;
  return status === "authenticated" ? "/progress" : "/login?google_error=session_unavailable";
}
