import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";
import { queryHarness, session, ApiError } from "./helpers/query-harness.mjs";

// Use the same runtime as the transpiled application modules.
const { QueryObserver, InfiniteQueryObserver, focusManager } = createRequire(import.meta.url)("@tanstack/react-query");
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const flush = async () => { for (let i = 0; i < 30; i++) await Promise.resolve(); };
const filters = { subject: "", reason: "all", state: "pending", offset: 0 };

test("notebook remounts show cached data immediately; stale reads refresh without hiding notes", async t => {
  let result = { items: ["saved note"] };
  const host = queryHarness(() => result);
  const api = host.api("notebook-api");
  await api.getNotebook("token", filters);
  const observer = new QueryObserver(host.client, api.notebookQuery("token", filters));
  const stop = observer.subscribe(() => {}); t.after(stop);
  assert.equal(observer.getCurrentResult().data.items[0], "saved note");
  assert.equal(host.calls.length, 1);
  const pending = deferred(); result = pending.promise;
  host.query.invalidateStudyQueries(["notebook"]);
  await flush();
  assert.equal(observer.getCurrentResult().isFetching, true);
  assert.equal(observer.getCurrentResult().data.items[0], "saved note");
  pending.resolve({ items: ["updated note"] }); await flush();
  assert.equal(observer.getCurrentResult().data.items[0], "updated note");
  await api.getNotebook("token", { ...filters, state: "resolved" });
  assert.equal(host.calls.length, 3);
});

test("token renewal retains private cache; logout clears it without removing public catalogues", async () => {
  const host = queryHarness(() => []);
  const api = host.api("study-api");
  await api.getSubjects(); await api.getProgressDashboard("token");
  const key = api.progressQuery("token").queryKey;
  await host.restoreAs(session("student", "renewed-secret-token"));
  assert.deepEqual(api.progressQuery("renewed-secret-token").queryKey, key);
  await api.getProgressDashboard("renewed-secret-token");
  assert.equal(host.calls.length, 2);
  assert.doesNotMatch(JSON.stringify(host.client.getQueryCache().getAll().map(q => q.queryKey)), /token/);
  host.controller.endSession();
  assert.equal(host.client.getQueryCache().findAll({ queryKey: ["private"] }).length, 0);
  assert.equal(host.client.getQueryCache().findAll({ queryKey: ["public"] }).length, 1);
  host.controller.completeAuthentication(session("other", "other-token"));
  assert.equal(host.client.getQueryData(api.progressQuery("other-token").queryKey), undefined);
});

test("late reads and plan writes cannot repopulate a signed-out account's cache", async () => {
  const pending = deferred();
  const host = queryHarness(() => pending.promise);
  const read = host.api("study-api").getProgressDashboard("token");
  const write = host.api("study-plan-api").sendStudyCheckin("token", "task", "dismiss");
  await flush();
  host.controller.endSession();
  pending.resolve({ today: "today", plan: null });
  await assert.rejects(read, /CancelledError|session has changed/);
  await assert.rejects(write, /session has changed/);
  assert.equal(host.client.getQueryCache().findAll({ queryKey: ["private"] }).length, 0);
  assert.equal(host.client.getMutationCache().getAll().length, 0);
});

test("a saved plan replaces an older pending GET and keeps its timer baseline", async () => {
  const pending = deferred(), saved = { preferences: { configured: true }, plan: { version: 2, tasks: [] } };
  const host = queryHarness((path, init) => init.method === "PATCH" ? saved : pending.promise);
  const api = host.api("study-plan-api");
  const oldRead = api.getReadyTodayPlan("token");
  const rejected = assert.rejects(oldRead, /CancelledError/);
  await api.changeStudyTask("token", "task", "start");
  const received = api.planReceivedAt(saved);
  pending.resolve({ preferences: { configured: false }, plan: null });
  await rejected; await flush();
  assert.equal(await api.getReadyTodayPlan("token"), saved);
  assert.equal(api.planReceivedAt(saved), received);
  assert.equal(host.calls.length, 2);
});

test("task and companion writes are serialized and the latest server result wins", async () => {
  const first = deferred(), second = { today: "after both", preferences: { configured: false }, plan: null };
  const host = queryHarness((path, init, count) => count === 1 ? first.promise : second);
  const api = host.api("study-plan-api");
  const one = api.changeStudyTask("token", "task", "start");
  const two = api.sendStudyCheckin("token", "task", "dismiss");
  await flush(); assert.equal(host.calls.length, 1);
  first.resolve({ ...second, today: "after first" });
  await Promise.all([one, two]);
  assert.equal(host.calls.length, 2);
  assert.equal((await api.getReadyTodayPlan("token")).today, "after both");
});

test("logout settles queued plan writes without sending them as another account", async () => {
  const first = deferred();
  const host = queryHarness(() => first.promise);
  const api = host.api("study-plan-api");
  const one = api.changeStudyTask("token", "task", "start");
  const two = api.sendStudyCheckin("token", "task", "dismiss");
  await flush();
  assert.equal(host.calls.length, 1);
  host.controller.endSession();
  host.controller.completeAuthentication(session("other", "other-token"));
  first.resolve({ plan: null });
  await Promise.all([assert.rejects(one, /session has changed/), assert.rejects(two, /session has changed/)]);
  assert.equal(host.calls.length, 1);
  assert.equal(host.client.getMutationCache().getAll().length, 0);
});

test("account changes during query cancellation cannot start a write or restore old data", async () => {
  for (const pauseAt of [1, 2]) {
    const host = queryHarness(() => ({ preferences: { configured: false }, plan: null }));
    const gate = deferred(), cancel = host.client.cancelQueries.bind(host.client);
    let cancellations = 0;
    host.client.cancelQueries = async (...args) => {
      await cancel(...args);
      if (++cancellations === pauseAt) await gate.promise;
    };
    const write = host.api("study-plan-api").changeStudyTask("token", "task", "start");
    await flush();
    host.controller.endSession();
    gate.resolve();
    await assert.rejects(write, /session has changed/);
    assert.equal(host.calls.length, pauseAt - 1);
    assert.equal(host.client.getQueryCache().findAll({ queryKey: ["private"] }).length, 0);
  }
});

test("completion and revision invalidate the dependent resources, including inactive pages", async () => {
  const host = queryHarness(() => ({}));
  const resources = ["today-plan", "roadmap", "progress", "practice-history", "availability", "notebook"];
  const seed = () => resources.forEach(name => host.client.setQueryData(host.query.privateKey(name), { saved: name }));
  const invalid = name => host.client.getQueryState(host.query.privateKey(name)).isInvalidated;
  seed();
  await host.api("study-api").completePracticeAttempt("token", "attempt", 120);
  assert.ok(resources.every(invalid));
  seed();
  await host.api("study-api").completePaperAttempt("token", "paper", 120);
  assert.ok(invalid("notebook") && invalid("progress"));
  assert.equal(invalid("today-plan"), false);
  seed();
  await host.api("notebook-api").finishRevision("token", "revision", 1, {});
  assert.equal(invalid("notebook"), true);
});

test("practice history keeps all loaded pages on revisit and refreshes them after a mutation", async t => {
  const host = queryHarness(path => {
    const offset = Number(new URL(`https://test${path}`).searchParams.get("offset"));
    return { items: [{ id: `attempt-${offset}` }], has_more: offset === 0, total: 2 };
  });
  const api = host.api("study-api"), options = api.practiceHistoryInfiniteQuery("token");
  const observer = new InfiniteQueryObserver(host.client, options);
  const stop = observer.subscribe(() => {}); t.after(stop);
  await observer.refetch(); await observer.fetchNextPage();
  assert.deepEqual(observer.getCurrentResult().data.pageParams, [0, 1]);
  assert.equal(observer.getCurrentResult().hasNextPage, false);
  const revisited = new InfiniteQueryObserver(host.client, options);
  assert.equal(revisited.getCurrentResult().data.pages.length, 2);
  assert.equal(host.calls.length, 2);
  host.query.invalidateStudyQueries(["practice-history"]); await flush();
  assert.equal(host.calls.length, 4);
});

test("background failures preserve visible data and focus refetches stale queries", async t => {
  let fail = false;
  const host = queryHarness(() => { if (fail) throw new ApiError("Offline", 0); return { completed_sets: 4 }; });
  const options = host.api("study-api").progressQuery("token");
  await host.client.fetchQuery(options);
  const observer = new QueryObserver(host.client, options);
  const stop = observer.subscribe(() => {}); t.after(stop);
  fail = true; await observer.refetch();
  assert.equal(observer.getCurrentResult().data.completed_sets, 4);
  assert.equal(observer.getCurrentResult().isError, true);
  fail = false;
  host.client.mount(); t.after(() => host.client.unmount());
  await host.client.invalidateQueries({ queryKey: options.queryKey, refetchType: "none" });
  focusManager.setFocused(false); focusManager.setFocused(true); await flush();
  assert.equal(observer.getCurrentResult().isError, false);
  assert.equal(host.calls.length, 3);
});

test("writes and the plan-creation query never automatically retry an ambiguous failure", async () => {
  const host = queryHarness((path, init) => {
    if (!init.method) return { preferences: { configured: true }, plan: null };
    throw new ApiError("Connection lost", 500);
  });
  const api = host.api("study-plan-api");
  await assert.rejects(api.getReadyTodayPlan("token"), /Connection lost/);
  assert.equal(host.calls.length, 2);
  await assert.rejects(api.changeStudyTask("token", "task", "start"), /Connection lost/);
  assert.equal(host.calls.length, 3);
});
