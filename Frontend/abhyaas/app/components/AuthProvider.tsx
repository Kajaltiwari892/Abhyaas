"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { authRedirect } from "@/lib/auth-routing";
import type { AcademyTarget } from "@/lib/academy-preference";
import {
  logoutAccount,
  restoreAuthSession,
  saveAcademyPreference,
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
  saveTargetAcademy: (target: AcademyTarget | null) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [session, setSession] = useState<AuthSession | null>(null);
  const preferenceVersion = useRef(0);
  const authVersion = useRef(0);
  const savingPreference = useRef(false);
  const redirectTo = authRedirect(pathname, status);

  const refreshSession = useCallback(async () => {
    const startedPreferenceVersion = preferenceVersion.current;
    const startedAuthVersion = authVersion.current;
    try {
      const restored = await restoreAuthSession();
      if (startedAuthVersion !== authVersion.current) return null;
      setSession((current) => {
        // A refresh started before a completed save must not restore the old target.
        if (restored && current?.user.id === restored.user.id
          && startedPreferenceVersion !== preferenceVersion.current) {
          return { ...restored, user: { ...restored.user, target_academy: current.user.target_academy } };
        }
        return restored;
      });
      setStatus(restored ? "authenticated" : "anonymous");
      return restored;
    } catch {
      if (startedAuthVersion !== authVersion.current) return null;
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
    if (redirectTo) router.replace(redirectTo);
  }, [redirectTo, router]);

  const completeAuthentication = useCallback((nextSession: AuthSession) => {
    authVersion.current += 1;
    setSession(nextSession);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(async () => {
    authVersion.current += 1;
    try {
      await logoutAccount();
    } finally {
      setSession(null);
      setStatus("anonymous");
      router.replace("/login");
    }
  }, [router]);

  const saveTargetAcademy = useCallback(async (target: AcademyTarget | null) => {
    if (!session) throw new Error("Sign in to save your preparation target.");
    if (savingPreference.current) throw new Error("Your target is already being saved.");
    savingPreference.current = true;
    const startedAuthVersion = authVersion.current;
    try {
      const updated = await saveAcademyPreference(session.access_token, target);
      if (startedAuthVersion !== authVersion.current) return;
      preferenceVersion.current += 1;
      setSession((current) => current?.user.id === updated.id
        ? { ...current, user: updated } : current);
    } finally {
      savingPreference.current = false;
    }
  }, [session]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: session?.user ?? null,
      accessToken: session?.access_token ?? null,
      completeAuthentication,
      refreshSession,
      signOut,
      saveTargetAcademy,
    }),
    [completeAuthentication, refreshSession, saveTargetAcademy, session, signOut, status],
  );

  if (redirectTo) {
    return <main className="auth-route-loading" aria-label="Checking your session"><span /><p>Opening Abhyaas…</p></main>;
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
