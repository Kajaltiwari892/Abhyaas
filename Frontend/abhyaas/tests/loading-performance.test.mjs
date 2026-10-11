import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { createRequestCache } from "../lib/request-cache.ts";
import { createSessionController } from "../lib/session-controller.ts";

const require = createRequire(import.meta.url);
const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
function load(path, resolve) {
  const compiled = ts.transpileModule(read(path), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  new Function("require", "module", "exports", compiled)(resolve, module, module.exports);
  return module.exports;
}
const session = (id, token = id) => ({ access_token: token, user: { id }, expires_at: new Date(Date.now() + 900_000).toISOString() });

test("simultaneous readers share one request and the cache expires", async () => {
  let now = 0, calls = 0;
  const cache = createRequestCache(100, 2, () => now);
  const pending = deferred();
  const fetch = () => { calls++; return pending.promise; };
  const one = cache.get("public", fetch), two = cache.get("public", fetch);
  pending.resolve("data");
  assert.deepEqual(await Promise.all([one, two]), ["data", "data"]);
  assert.equal(await cache.get("public", fetch), "data");
  assert.equal(calls, 1);
  now = 100;
  await cache.get("public", fetch);
  assert.equal(calls, 2);
});

test("one cancelled subscriber cannot cancel another subscriber", async () => {
  const cache = createRequestCache(100), pending = deferred(), controller = new AbortController();
  let calls = 0;
  const fetch = () => { calls++; return pending.promise; };
  const one = cache.get("plan", fetch, controller.signal), two = cache.get("plan", fetch);
  controller.abort();
  await assert.rejects(one, { name: "AbortError" });
  pending.resolve({ done: false });
  assert.deepEqual(await two, { done: false });
  assert.equal(calls, 1);
  await assert.rejects(cache.get("plan", fetch, controller.signal), { name: "AbortError" });
});

test("failures retry and old requests cannot overwrite mutations or resurrect a cleared cache", async () => {
  const cache = createRequestCache(100), old = deferred();
  const request = cache.get("plan", () => old.promise);
  await flush();
  cache.set("plan", "updated");
  old.resolve("stale"); await request;
  assert.equal(await cache.get("plan", async () => "wrong"), "updated");
  const other = deferred();
  const signedOutRequest = cache.get("private", () => other.promise);
  await flush(); cache.clear(); other.resolve("old account"); await signedOutRequest;
  assert.equal(await cache.get("private", async () => "new account"), "new account");
  await assert.rejects(cache.get("failed", async () => { throw Error("offline"); }));
  assert.equal(await cache.get("failed", async () => "recovered"), "recovered");
});

test("cache storage is bounded", async () => {
  const cache = createRequestCache(100, 1);
  cache.set("first", 1); cache.set("second", 2);
  assert.equal(await cache.get("first", async () => 3), 3);
});

function planApi(handler) {
  const controller = createSessionController(async () => null);
  controller.completeAuthentication(session("student", "token"));
  const calls = [];
  const api = load("../lib/study-plan-api.ts", id => id === "./request-cache" ? { createRequestCache }
    : { ApiError: Error, sessionController: controller, apiRequest: async (path, init) => { calls.push({ path, init }); return handler(path, init); } });
  return { api, controller, calls };
}

test("planner and companion share both the read and required creation; timers retain the original receive time", async () => {
  const pending = deferred(), ready = { preferences: { configured: true }, plan: { version: 2 } };
  const { api, calls } = planApi((path, init) => init.method === "POST" ? ready : pending.promise);
  const controller = new AbortController();
  const one = api.getReadyTodayPlan("token", controller.signal), two = api.getReadyTodayPlan("token");
  controller.abort(); await assert.rejects(one, { name: "AbortError" });
  pending.resolve({ preferences: { configured: true }, plan: null });
  assert.equal(await two, ready);
  assert.equal(calls.length, 2);
  assert.equal(calls[0].init.signal.aborted, false);
  const timestamp = api.planReceivedAt(ready);
  assert.equal(await api.getReadyTodayPlan("token"), ready);
  assert.equal(api.planReceivedAt(ready), timestamp);
  assert.equal(calls.length, 2);
});

test("saving a task supplies fresh cached data; account changes and sign-out discard private plans", async () => {
  let result = { preferences: { configured: false }, plan: null, today: "before" };
  const { api, controller, calls } = planApi(() => result);
  await api.getReadyTodayPlan("token");
  result = { ...result, today: "updated" };
  await api.changeStudyTask("token", "task", "complete");
  assert.equal((await api.getReadyTodayPlan("token")).today, "updated");
  assert.equal(calls.length, 2);
  controller.completeAuthentication(session("other", "other-token"));
  result = { ...result, today: "other account" };
  assert.equal((await api.getReadyTodayPlan("other-token")).today, "other account");
  controller.endSession(); controller.completeAuthentication(session("student", "new-token"));
  result = { ...result, today: "signed in again" };
  assert.equal((await api.getReadyTodayPlan("new-token")).today, "signed in again");
  assert.equal(calls.length, 4);
});

test("sign-out during a pending read cannot create a plan with the previous account's token", async () => {
  const pending = deferred();
  const { api, controller, calls } = planApi(() => pending.promise);
  const read = api.getReadyTodayPlan("token");
  await flush(); controller.endSession();
  pending.resolve({ preferences: { configured: true }, plan: null });
  await assert.rejects(read, /session has changed/);
  assert.equal(calls.length, 1);
});

test("public catalogues reuse requests without mixing paper filters or caching private progress", async () => {
  const calls = [];
  const api = load("../lib/study-api.ts", id => id === "./request-cache" ? { createRequestCache }
    : id === "./study-plan-api" ? { invalidateTodayPlan() {} }
    : { apiRequest: async path => { calls.push(path); return []; } });
  await Promise.all([api.getSubjects(), api.getSubjects()]); await api.getSubjects();
  await Promise.all([api.getPapers({ year: 2026 }), api.getPapers({ year: 2026 })]);
  await api.getPapers({ year: 2025 });
  await api.getProgressDashboard("a"); await api.getProgressDashboard("b");
  assert.deepEqual(calls, ["/catalog/subjects", "/papers?year=2026", "/papers?year=2025", "/progress/dashboard", "/progress/dashboard"]);
});

test("initial session loading renders a public skeleton, never private data or protected children", () => {
  const Skeleton = load("../app/components/WorkspaceSkeleton.tsx", id => id.endsWith(".css")
    ? { default: new Proxy({}, { get: (_, key) => String(key) }) }
    : id === "next/link" ? { default: ({ children, ...props }) => createElement("a", props, children) } : require(id)).default;
  const html = renderToStaticMarkup(createElement(Skeleton, { pathname: "/progress" }));
  assert.match(html, /Opening your study space/);
  assert.match(html, /aria-busy="true"/);
  assert.match(html, /Study navigation/);
  assert.doesNotMatch(html, /localStorage|completed sets|<button|@example/);
  const provider = read("../app/components/AuthProvider.tsx");
  assert.ok(provider.indexOf("<WorkspaceSkeleton") < provider.indexOf("{children}"));
  assert.match(provider, /shouldWaitForSession\(pathname, status\)/);
  assert.match(read("../app/components/workspace-skeleton.module.css"), /prefers-reduced-motion/);
});
