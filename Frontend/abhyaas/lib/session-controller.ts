import type { AuthSession, AuthUser } from "./auth-api";

export type AuthStatus = "loading" | "authenticated" | "anonymous" | "unavailable";
export type SessionSnapshot = {
  status: AuthStatus;
  session: AuthSession | null;
  retryCount: number;
};

export const initialSessionSnapshot: SessionSnapshot = {
  status: "loading", session: null, retryCount: 0,
};

export function nextRefreshDelay(snapshot: SessionSnapshot, now = Date.now()): number | null {
  if (snapshot.retryCount) return Math.min(60_000, 5_000 * 2 ** Math.min(snapshot.retryCount - 1, 4));
  if (!snapshot.session) return null;
  return Math.max(1_000, Date.parse(snapshot.session.expires_at) - now - 60_000);
}

// In-memory only. The persistent credential stays in the server's HttpOnly cookie.
// A network error is deliberately different from a confirmed invalid session (null).
export function createSessionController(restore: () => Promise<AuthSession | null>) {
  let snapshot = initialSessionSnapshot;
  let generation = 0;
  let userVersion = 0;
  let pending: Promise<AuthSession | null> | null = null;
  const listeners = new Set<() => void>();
  const tokens = new Set<string>();
  const publish = (next: SessionSnapshot) => {
    snapshot = next;
    for (const listener of listeners) listener();
  };
  const remember = (session: AuthSession) => {
    tokens.add(session.access_token);
    if (tokens.size > 16) tokens.delete(tokens.values().next().value!);
  };
  const controller = {
    getSnapshot: () => snapshot,
    getGeneration: () => generation,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },
    ownsToken: (token: string) => tokens.has(token),
    completeAuthentication(session: AuthSession) {
      generation += 1;
      tokens.clear();
      remember(session);
      publish({ status: "authenticated", session, retryCount: 0 });
    },
    endSession() {
      generation += 1;
      tokens.clear();
      publish({ status: "anonymous", session: null, retryCount: 0 });
    },
    updateUser(user: AuthUser, expectedGeneration: number) {
      if (expectedGeneration !== generation || snapshot.session?.user.id !== user.id) return;
      userVersion += 1;
      publish({ ...snapshot, session: { ...snapshot.session, user } });
    },
    refresh(): Promise<AuthSession | null> {
      if (pending) return pending;
      const startedGeneration = generation;
      const startedUserVersion = userVersion;
      const task = (async () => {
        try {
          let restored = await restore();
          if (generation !== startedGeneration) return snapshot.session;
          if (!restored) {
            controller.endSession();
            return null;
          }
          if (snapshot.session && restored.user.id !== snapshot.session.user.id) {
            generation += 1;
            tokens.clear();
          } else if (startedUserVersion !== userVersion && snapshot.session) {
            restored = { ...restored, user: snapshot.session.user };
          }
          remember(restored);
          publish({ status: "authenticated", session: restored, retryCount: 0 });
          return restored;
        } catch (error) {
          if (generation !== startedGeneration) return snapshot.session;
          publish({
            status: snapshot.session ? "authenticated" : "unavailable",
            session: snapshot.session,
            retryCount: snapshot.retryCount + 1,
          });
          throw error;
        }
      })();
      pending = task.finally(() => { pending = null; });
      return pending;
    },
  };
  return controller;
}
