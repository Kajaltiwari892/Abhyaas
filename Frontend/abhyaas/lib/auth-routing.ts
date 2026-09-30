type AuthStatus = "loading" | "authenticated" | "anonymous";

const publicPaths = new Set(["/", "/login", "/about", "/privacy", "/auth/callback"]);

// Home is always the public landing page. Never gate it on a session request or
// read window.location during rendering (it can lag behind a client transition).
export function authRedirect(pathname: string, status: AuthStatus): string | null {
  if (status === "loading") return null;
  if (status === "authenticated" && ["/login", "/auth/callback"].includes(pathname)) {
    return "/progress";
  }
  if (status === "anonymous" && !publicPaths.has(pathname)) {
    return `/login?next=${encodeURIComponent(pathname)}`;
  }
  return null;
}
