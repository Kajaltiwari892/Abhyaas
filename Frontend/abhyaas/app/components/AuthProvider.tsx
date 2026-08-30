"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  logoutAccount,
  restoreAuthSession,
  type AuthSession,
  type AuthUser,
} from "@/lib/auth-api";

type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  accessToken: string | null;
  completeAuthentication: (session: AuthSession) => void;
  refreshSession: () => Promise<AuthSession | null>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);
const PUBLIC_PATHS = new Set(["/", "/login", "/about", "/privacy", "/auth/callback"]);

function isProtectedPath(pathname: string) {
  return !PUBLIC_PATHS.has(pathname);
}

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [session, setSession] = useState<AuthSession | null>(null);

  const refreshSession = useCallback(async () => {
    try {
      const restored = await restoreAuthSession();
      setSession(restored);
      setStatus(restored ? "authenticated" : "anonymous");
      return restored;
    } catch {
      setSession(null);
      setStatus("anonymous");
      return null;
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void refreshSession());
  }, [refreshSession]);

  useEffect(() => {
    if (!session) return;
    const refreshIn = Math.max(1_000, new Date(session.expires_at).getTime() - Date.now() - 60_000);
    const timer = window.setTimeout(() => void refreshSession(), refreshIn);
    return () => window.clearTimeout(timer);
  }, [refreshSession, session]);

  useEffect(() => {
    if (!session) return;

    const refreshExpiredAccessToken = () => {
      const refreshThreshold = Date.now() + 60_000;
      if (new Date(session.expires_at).getTime() <= refreshThreshold) {
        void refreshSession();
      }
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") refreshExpiredAccessToken();
    };

    window.addEventListener("focus", refreshExpiredAccessToken);
    window.addEventListener("pageshow", refreshExpiredAccessToken);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.removeEventListener("focus", refreshExpiredAccessToken);
      window.removeEventListener("pageshow", refreshExpiredAccessToken);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [refreshSession, session]);

  useEffect(() => {
    if (status === "loading") return;

    if (status === "authenticated" && ["/login", "/auth/callback"].includes(pathname)) {
      router.replace("/progress");
      return;
    }

    if (status === "anonymous" && isProtectedPath(pathname)) {
      const destination = encodeURIComponent(pathname);
      router.replace(`/login?next=${destination}`);
    }
  }, [pathname, router, status]);

  const completeAuthentication = useCallback((nextSession: AuthSession) => {
    setSession(nextSession);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logoutAccount();
    } finally {
      setSession(null);
      setStatus("anonymous");
      router.replace("/login");
    }
  }, [router]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: session?.user ?? null,
      accessToken: session?.access_token ?? null,
      completeAuthentication,
      refreshSession,
      signOut,
    }),
    [completeAuthentication, refreshSession, session, signOut, status],
  );

  const redirectingAuthenticatedUser =
    status === "authenticated" && ["/login", "/auth/callback"].includes(pathname);
  const redirectingAnonymousUser = status === "anonymous" && isProtectedPath(pathname);

  if (status === "loading" || redirectingAuthenticatedUser || redirectingAnonymousUser) {
    return <main className="auth-route-loading" aria-label="Checking your session"><span /><p>Opening Abhyaas…</p></main>;
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
