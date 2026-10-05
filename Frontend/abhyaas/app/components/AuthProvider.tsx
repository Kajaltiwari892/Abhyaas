"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import { toast } from "sonner";
import { authRedirect, shouldShowSessionRecovery, shouldWaitForSession } from "@/lib/auth-routing";
import { initialSessionSnapshot, nextRefreshDelay, type AuthStatus } from "@/lib/session-controller";
import type { AcademyTarget } from "@/lib/academy-preference";
import {
  logoutAccount,
  restoreAuthSession,
  saveAcademyPreference,
  sessionController,
  type AuthSession,
  type AuthUser,
} from "@/lib/auth-api";
import styles from "./SessionRecovery.module.css";

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
const serverSnapshot = () => initialSessionSnapshot;
const retryInBackground = () => { void restoreAuthSession().catch(() => {}); };

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const snapshot = useSyncExternalStore(sessionController.subscribe, sessionController.getSnapshot, serverSnapshot);
  const { status, session, retryCount } = snapshot;
  const savingPreference = useRef(false);
  const signingOut = useRef(false);
  const redirectTo = authRedirect(pathname, status);

  const refreshSession = restoreAuthSession;

  useEffect(() => {
    let active = true;
    queueMicrotask(() => { if (active) retryInBackground(); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const refreshIn = nextRefreshDelay(snapshot);
    if (refreshIn === null) return;
    const timer = window.setTimeout(retryInBackground, refreshIn);
    return () => window.clearTimeout(timer);
  }, [snapshot]);

  useEffect(() => {
    const refreshExpiredAccessToken = () => {
      const current = sessionController.getSnapshot();
      const refreshThreshold = Date.now() + 60_000;
      if (current.retryCount || (current.session && Date.parse(current.session.expires_at) <= refreshThreshold)) {
        retryInBackground();
      }
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") refreshExpiredAccessToken();
    };

    window.addEventListener("focus", refreshExpiredAccessToken);
    window.addEventListener("pageshow", refreshExpiredAccessToken);
    window.addEventListener("online", refreshExpiredAccessToken);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.removeEventListener("focus", refreshExpiredAccessToken);
      window.removeEventListener("pageshow", refreshExpiredAccessToken);
      window.removeEventListener("online", refreshExpiredAccessToken);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  useEffect(() => {
    if (redirectTo) router.replace(redirectTo);
  }, [redirectTo, router]);

  const completeAuthentication = useCallback((nextSession: AuthSession) => {
    sessionController.completeAuthentication(nextSession);
  }, []);

  const signOut = useCallback(async () => {
    if (signingOut.current) return;
    signingOut.current = true;
    try {
      await logoutAccount();
      router.replace("/login");
    } catch {
      toast.error("Couldn't confirm sign out", { description: "Check your connection and try again." });
    } finally {
      signingOut.current = false;
    }
  }, [router]);

  const saveTargetAcademy = useCallback(async (target: AcademyTarget | null) => {
    if (!session) throw new Error("Sign in to save your preparation target.");
    if (savingPreference.current) throw new Error("Your target is already being saved.");
    savingPreference.current = true;
    const startedAuthVersion = sessionController.getGeneration();
    try {
      const updated = await saveAcademyPreference(session.access_token, target);
      sessionController.updateUser(updated, startedAuthVersion);
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

  if (shouldShowSessionRecovery(pathname, status)) {
    return <main className={styles.recovery}>
      <div role="status" aria-live="polite">
        <h1>Let’s reconnect</h1>
        <p>We couldn’t check your session. This doesn’t mean you’ve been signed out.</p>
        <p>We’ll retry automatically when your connection is available.</p>
      </div>
      <button type="button" onClick={retryInBackground}>Retry connection</button>
    </main>;
  }

  if (redirectTo || shouldWaitForSession(pathname, status)) {
    return <main className="auth-route-loading" role="status" aria-live="polite"><span aria-hidden="true" /><p>{redirectTo ? "Opening Abhyaas…" : "Checking your session…"}</p></main>;
  }

  return <AuthContext.Provider value={value}>
    {children}
    {session && retryCount > 0 && <aside className={styles.notice} role="status" aria-live="polite">
      <p>Connection interrupted. Reconnecting without signing you out.</p>
      <button type="button" onClick={retryInBackground}>Retry</button>
    </aside>}
  </AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
