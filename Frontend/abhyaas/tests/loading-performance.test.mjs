import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { queryHarness } from "./helpers/query-harness.mjs";

const require = createRequire(import.meta.url);
const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
function load(path, resolve) {
  const compiled = ts.transpileModule(read(path), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const loaded = { exports: {} };
  new Function("require", "module", "exports", compiled)(resolve, loaded, loaded.exports);
  return loaded.exports;
}
const session = (id, token = id) => ({ access_token: token, user: { id }, expires_at: new Date(Date.now() + 900_000).toISOString() });

function planApi(handler) {
  const host = queryHarness(handler);
  return { ...host, api: host.api("study-plan-api") };
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
  await assert.rejects(read, error => /CancelledError|session has changed/.test(error.message));
  assert.equal(calls.length, 1);
});

test("public catalogues share queries while private progress is scoped to each login", async () => {
  const host = queryHarness(() => []);
  const api = host.api("study-api");
  await Promise.all([api.getSubjects(), api.getSubjects()]); await api.getSubjects();
  await Promise.all([api.getPapers({ year: 2026 }), api.getPapers({ year: 2026 })]);
  await api.getPapers({ year: 2025 });
  await api.getProgressDashboard("token"); await api.getProgressDashboard("token");
  host.controller.completeAuthentication(session("other", "other-token"));
  await api.getProgressDashboard("other-token");
  assert.deepEqual(host.calls.map(call => call.path), ["/catalog/subjects", "/papers?year=2026", "/papers?year=2025", "/progress/dashboard", "/progress/dashboard"]);
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
