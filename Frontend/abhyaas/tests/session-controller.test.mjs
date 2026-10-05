import test from "node:test";
import assert from "node:assert/strict";
import { createSessionController, nextRefreshDelay } from "../lib/session-controller.ts";
import { authRedirect, googleCallbackRedirect, shouldShowSessionRecovery } from "../lib/auth-routing.ts";

const session = (token = "first", user = "student") => ({
  access_token: token, token_type: "bearer", expires_at: "2026-10-05T12:15:00Z",
  user: { id: user, email: `${user}@example.com`, name: "Student", target_academy: null },
});
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};

test("network/server failure retains an existing session and retries with backoff", async () => {
  const store = createSessionController(async () => { throw Error("offline"); });
  store.completeAuthentication(session());
  await assert.rejects(store.refresh(), /offline/);
  assert.equal(store.getSnapshot().status, "authenticated");
  assert.equal(store.getSnapshot().session.access_token, "first");
  assert.equal(nextRefreshDelay(store.getSnapshot()), 5_000);
  await assert.rejects(store.refresh());
  assert.equal(nextRefreshDelay(store.getSnapshot()), 10_000);
  assert.equal(nextRefreshDelay({ ...store.getSnapshot(), retryCount: 99 }), 60_000);
});

test("browser reopening while offline is recoverable, not a logout", async () => {
  let online = false;
  const store = createSessionController(async () => {
    if (!online) throw Error("offline");
    return session("restored");
  });
  await assert.rejects(store.refresh());
  assert.equal(store.getSnapshot().status, "unavailable");
  assert.equal(authRedirect("/progress", "unavailable"), null);
  assert.equal(googleCallbackRedirect("unavailable", null), null);
  for (const path of ["/progress", "/login", "/auth/callback"]) {
    assert.equal(shouldShowSessionRecovery(path, "unavailable"), true);
  }
  for (const path of ["/", "/about", "/privacy"]) {
    assert.equal(shouldShowSessionRecovery(path, "unavailable"), false);
  }
  online = true;
  await store.refresh();
  assert.equal(store.getSnapshot().status, "authenticated");
  assert.equal(store.getSnapshot().retryCount, 0);
});

test("only a confirmed invalid refresh session signs the student out", async () => {
  const store = createSessionController(async () => null);
  store.completeAuthentication(session());
  await store.refresh();
  assert.equal(store.getSnapshot().status, "anonymous");
  assert.equal(store.getSnapshot().session, null);
  assert.equal(nextRefreshDelay(store.getSnapshot()), null);
});

test("overlapping callers share one renewal", async () => {
  const result = deferred();
  let calls = 0;
  const store = createSessionController(() => { calls++; return result.promise; });
  const first = store.refresh();
  const second = store.refresh();
  assert.equal(first, second);
  result.resolve(session());
  await first;
  assert.equal(calls, 1);
});

test("an old pending refresh cannot undo logout or a different sign-in", async () => {
  for (const action of ["logout", "login"]) {
    const result = deferred();
    const store = createSessionController(() => result.promise);
    store.completeAuthentication(session());
    const pending = store.refresh();
    if (action === "logout") store.endSession();
    else store.completeAuthentication(session("new-account", "other"));
    result.resolve(session("stale"));
    await pending;
    assert.equal(store.getSnapshot().session?.access_token ?? null, action === "logout" ? null : "new-account");
    assert.equal(store.ownsToken("first"), false);
  }
});

test("late errors from an old login do not affect the current account", async () => {
  const result = deferred();
  const store = createSessionController(() => result.promise);
  const pending = store.refresh();
  store.completeAuthentication(session());
  result.reject(Error("old request failed"));
  await pending;
  assert.equal(store.getSnapshot().status, "authenticated");
  assert.equal(store.getSnapshot().retryCount, 0);
});

test("renewal preserves a target saved after the request started", async () => {
  const result = deferred();
  const store = createSessionController(() => result.promise);
  store.completeAuthentication(session());
  const pending = store.refresh();
  store.updateUser({ ...session().user, target_academy: "OTA" }, store.getGeneration());
  result.resolve(session("renewed"));
  await pending;
  assert.equal(store.getSnapshot().session.user.target_academy, "OTA");
  assert.equal(store.getSnapshot().session.access_token, "renewed");
});

test("normal renewal is scheduled one minute before the 15-minute access expiry", () => {
  const store = createSessionController(async () => session());
  store.completeAuthentication(session());
  assert.equal(nextRefreshDelay(store.getSnapshot(), Date.parse("2026-10-05T12:00:00Z")), 14 * 60_000);
  assert.equal(nextRefreshDelay(store.getSnapshot(), Date.parse("2026-10-05T12:20:00Z")), 1_000);
});
