import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
import { createSessionController } from "../lib/session-controller.ts";

const source = readFileSync(new URL("../lib/auth-api.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const makeSession = (token, expires = Date.now() + 900_000, id = "student") => ({
  access_token: token, token_type: "bearer", expires_at: new Date(expires).toISOString(),
  user: { id, name: "Student", email: `${id}@example.com`, target_academy: null },
});
const reply = (status, data) => new Response(JSON.stringify(data), { status });
function loadApi(fetch) {
  const exports = {};
  // Exercise the real API wrapper without touching the network or browser cookies.
  new Function("exports", "require", "fetch", "navigator", "setTimeout", compiled)(
    exports, () => ({ createSessionController }), fetch, undefined,
    (fn) => setTimeout(fn, 0), // Skip the HTTP retry delay, not token-expiry checks.
  );
  return exports;
}

test("a protected 401 renews the session and retries once with the fresh token", async () => {
  const calls = [];
  const api = loadApi(async (url, init) => {
    calls.push([url.split("/api/v1")[1], new Headers(init.headers).get("Authorization")]);
    if (url.endsWith("/auth/refresh")) return reply(200, makeSession("fresh"));
    return calls.length === 1 ? reply(401, { detail: "Expired" }) : reply(200, { saved: true });
  });
  api.sessionController.completeAuthentication(makeSession("old"));
  assert.deepEqual(await api.apiRequest("/attempts", { method: "POST", headers: { Authorization: "Bearer old" }, body: "{}" }), { saved: true });
  assert.deepEqual(calls, [["/attempts", "Bearer old"], ["/auth/refresh", null], ["/attempts", "Bearer fresh"]]);
});

test("returning after access expiry renews before making a protected request", async () => {
  const calls = [];
  const api = loadApi(async (url, init) => {
    calls.push([url, new Headers(init.headers).get("Authorization")]);
    return url.endsWith("/auth/refresh") ? reply(200, makeSession("fresh")) : reply(200, {});
  });
  api.sessionController.completeAuthentication(makeSession("old", Date.now() - 1));
  await api.apiRequest("/users/me", { headers: { Authorization: "Bearer old" } });
  assert.equal(calls.length, 2);
  assert.ok(calls[0][0].endsWith("/auth/refresh"));
  assert.equal(calls[1][1], "Bearer fresh");
});

test("network/500 failures of a write are never automatically replayed", async () => {
  for (const kind of ["network", "server"]) {
    let calls = 0;
    const api = loadApi(async () => {
      calls++;
      if (kind === "network") throw Error("connection lost after save");
      return reply(500, { detail: "Unavailable" });
    });
    api.sessionController.completeAuthentication(makeSession("old"));
    await assert.rejects(api.apiRequest("/attempts", { method: "POST", headers: { Authorization: "Bearer old" } }));
    assert.equal(calls, 1);
    assert.equal(api.sessionController.getSnapshot().status, "authenticated");
  }
});

test("a failed refresh can recover on retry without losing authentication", async () => {
  let calls = 0;
  const api = loadApi(async () => {
    calls++;
    return calls === 1 ? reply(503, {}) : reply(200, makeSession("recovered"));
  });
  api.sessionController.completeAuthentication(makeSession("old"));
  assert.equal((await api.restoreAuthSession()).access_token, "recovered");
  assert.equal(calls, 2);
});

test("exhausted network retries preserve auth; a refresh 401 signs out without looping", async () => {
  for (const status of [503, 401]) {
    let calls = 0;
    const api = loadApi(async () => { calls++; return reply(status, {}); });
    api.sessionController.completeAuthentication(makeSession("old"));
    if (status === 503) await assert.rejects(api.restoreAuthSession());
    else assert.equal(await api.restoreAuthSession(), null);
    assert.equal(calls, status === 503 ? 2 : 1);
    assert.equal(api.sessionController.getSnapshot().status, status === 503 ? "authenticated" : "anonymous");
  }
});

test("a repeated protected 401 stops after one replay", async () => {
  let requests = 0;
  const api = loadApi(async (url) => {
    if (url.endsWith("/auth/refresh")) return reply(200, makeSession("fresh"));
    requests++;
    return reply(401, {});
  });
  api.sessionController.completeAuthentication(makeSession("old"));
  await assert.rejects(api.apiRequest("/users/me", { headers: { Authorization: "Bearer old" } }));
  assert.equal(requests, 2);
});

test("an account change while renewing cannot replay an old write as the new user", async () => {
  let requests = 0;
  let api;
  api = loadApi(async (url) => {
    if (url.endsWith("/auth/refresh")) {
      api.sessionController.completeAuthentication(makeSession("other", undefined, "other-user"));
      return reply(200, makeSession("stale"));
    }
    requests++;
    return reply(401, {});
  });
  api.sessionController.completeAuthentication(makeSession("old"));
  await assert.rejects(api.apiRequest("/attempts", { method: "POST", headers: { Authorization: "Bearer old" } }));
  assert.equal(requests, 1);
  assert.equal(api.sessionController.getSnapshot().session.user.id, "other-user");
});

test("cancelling a request prevents its replay after renewal", async () => {
  const abort = new AbortController();
  let requests = 0;
  const api = loadApi(async (url) => {
    if (url.endsWith("/auth/refresh")) {
      abort.abort();
      return reply(200, makeSession("fresh"));
    }
    requests++;
    return reply(401, {});
  });
  api.sessionController.completeAuthentication(makeSession("old"));
  await assert.rejects(api.apiRequest("/users/me", { signal: abort.signal, headers: { Authorization: "Bearer old" } }));
  assert.equal(requests, 1);
});

test("failed logout does not pretend success; confirmed logout clears local state", async () => {
  for (const status of [503, 200]) {
    const api = loadApi(async () => reply(status, {}));
    api.sessionController.completeAuthentication(makeSession("old"));
    if (status === 503) await assert.rejects(api.logoutAccount());
    else await api.logoutAccount();
    assert.equal(api.sessionController.getSnapshot().status, status === 503 ? "authenticated" : "anonymous");
  }
});
