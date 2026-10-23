import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { queryHarness } from "./helpers/query-harness.mjs";
import { createLatestSaveQueue } from "../lib/latest-save-queue.ts";

const require = createRequire(import.meta.url);
const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
const css = { default: new Proxy({}, { get: (_, key) => String(key) }) };
function load(path, resolve = require, globals = {}) {
  const compiled = ts.transpileModule(read(path), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const loaded = { exports: {} };
  new Function("require", "module", "exports", ...Object.keys(globals), compiled)(resolve, loaded, loaded.exports, ...Object.values(globals));
  return loaded.exports;
}
const Skeleton = load("../app/practice/PracticeQuestionSkeleton.tsx", id => id.endsWith(".css") ? css : require(id)).default;
const task = { id: "daily-1", subject_slug: "english", subject_name: "English", topic_slug: "grammar", topic_name: "Grammar", study_done: true, question_count: 50, quiz_remaining: 50, quiz_answered: 0, quiz_status: null };
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };

test("question skeleton has four decorative options, honest status and no fake timer/actions", () => {
  const html = renderToStaticMarkup(createElement(Skeleton, { count: 50, subject: "English", topic: "Grammar" }));
  assert.match(html, /Preparing your 50-question quiz/);
  assert.match(html, /English · Grammar/);
  assert.match(html, /aria-busy="true"/);
  assert.match(html, /role="status" aria-live="polite"/);
  assert.match(html, /class="preview" aria-hidden="true"/);
  assert.equal((html.match(/class="option"/g) ?? []).length, 4);
  assert.doesNotMatch(html, /<button|role="progressbar"|50:00/);
  const delayed = renderToStaticMarkup(createElement(Skeleton, { delayed: true }));
  assert.match(delayed, /Still preparing your questions/);
  assert.match(delayed, /go back and try again later/);
});

// Run the real workspace handlers with deferred APIs and a small deterministic
// hook host. No server requests, generated question quota or browser login needed.
function workspaceHost() {
  const slots = [], effects = [], requests = [], saves = [], completions = [], catalogueCalls = [], timers = new Map();
  let cursor = 0, timerId = 0;
  const hooks = {
    useState(initial) {
      const i = cursor++;
      if (!slots[i]) slots[i] = { value: typeof initial === "function" ? initial() : initial };
      return [slots[i].value, value => { slots[i].value = typeof value === "function" ? value(slots[i].value) : value; }];
    },
    useRef(initial) { const i = cursor++; return slots[i] ??= { current: initial }; },
    useCallback(fn, deps) {
      const i = cursor++;
      if (!slots[i] || deps.some((value, n) => !Object.is(value, slots[i].deps[n]))) slots[i] = { value: fn, deps };
      return slots[i].value;
    },
    useEffect(fn, deps) {
      const i = cursor++;
      const previous = effects[i];
      const changed = !previous || deps.some((value, n) => !Object.is(value, previous.deps[n]));
      effects[i] = { fn, deps, cleanup: previous?.cleanup, pending: changed };
    },
  };
  const window = {
    setTimeout(fn, ms) { const id = ++timerId; timers.set(id, { fn, ms }); return id; },
    clearTimeout(id) { timers.delete(id); },
    setInterval() { return ++timerId; }, clearInterval() {},
    addEventListener() {}, removeEventListener() {},
  };
  const planApi = {
    startDailyQuiz(token, id, signal, onProgress) { const request = deferred(); requests.push({ ...request, token, id, signal, onProgress }); return request.promise; },
  };
  const studyApi = {
    subjectsQuery: () => ({}),
    practiceHistoryInfiniteQuery: () => ({}),
    getSubjects: () => { catalogueCalls.push("subjects"); return new Promise(() => {}); },
    getPracticeAvailability: async () => { catalogueCalls.push("availability"); return { total: 80, unseen: 80 }; },
    checkpointPracticeAttempt(...input) { const result = deferred(); saves.push({ ...result, input }); return result.promise; },
    completePracticeAttempt(...input) { const result = deferred(); completions.push({ ...result, input }); return result.promise; },
  };
  const practicePlan = load("../lib/practice-plan.ts");
  const academy = load("../lib/academy-preference.ts");
  const Workspace = load("../app/practice/PracticeWorkspace.tsx", id => {
    if (id === "react") return hooks;
    if (id === "@tanstack/react-query") return { useQuery: () => ({}), useInfiniteQuery: () => ({}) };
    if (id.endsWith(".css")) return css;
    if (id === "./PracticeQuestionSkeleton") return { default: Skeleton };
    if (id === "@/lib/study-api") return studyApi;
    if (id === "@/lib/latest-save-queue") return { createLatestSaveQueue };
    if (id === "@/lib/study-plan-api") return planApi;
    if (id === "@/lib/practice-plan") return practicePlan;
    if (id === "@/lib/academy-preference") return academy;
    if (id.endsWith("AuthProvider")) return { useAuth: () => ({ accessToken: "test-token", user: { id: "student", target_academy: "OTA" } }) };
    if (id.endsWith("PreparationTarget")) return { default: () => null };
    if (id === "next/navigation") return { useRouter: () => ({ push() {} }) };
    if (id === "next/link") return { default: ({ children, href }) => createElement("a", { href }, children) };
    return require(id);
  }, { window }).default;
  function render() { cursor = 0; return Workspace({ initialSubject: "english", dailyTask: task }); }
  function runEffects(force = false) { for (const effect of effects) { if (!effect || !force && !effect.pending) continue; effect.cleanup?.(); effect.cleanup = effect.fn(); effect.pending = false; } }
  function cleanup() { for (const effect of effects) effect?.cleanup?.(); }
  return { render, runEffects, cleanup, requests, saves, completions, catalogueCalls, timers };
}
function button(tree, text) {
  if (!tree || typeof tree !== "object") return;
  if (Array.isArray(tree)) { for (const child of tree) { const found = button(child, text); if (found) return found; } return; }
  if (tree.type === "button" && renderToStaticMarkup(tree).includes(text)) return tree.props.onClick;
  return button(tree.props?.children, text);
}
function attempt(changes = {}) {
  return { id: "saved-quiz", subject_slug: "english", questions: Array.from({ length: 50 }, (_, i) => ({ id: `q${i}`, topic: "Grammar", prompt: `Saved question ${i + 1}`, options: ["One", "Two", "Three", "Four"], source_label: "Practice", provenance: null })), answers: [{ question_id: "q2", selected_index: 1, marked_for_review: true }], current_position: 2, duration_seconds: 3000, elapsed_seconds: 300, negative_mark_fraction: 1 / 3, ...changes };
}

test("daily quiz opens immediately and starts once under development effect replay", async () => {
  const host = workspaceHost();
  const html = renderToStaticMarkup(host.render());
  assert.match(html, /Preparing your 50-question quiz/);
  assert.doesNotMatch(html, /Start 50-question quiz|Ready to practise/);
  host.runEffects(); host.cleanup(); host.runEffects(true);
  await flush();
  assert.equal(host.requests.length, 1);
  assert.equal(host.requests[0].id, task.id);
  assert.equal(host.requests[0].signal.aborted, false);
  assert.deepEqual(host.catalogueCalls, []); // No unrelated request can block or error this quiz.
  host.render(); host.runEffects(); await flush();
  assert.equal(host.requests.length, 1);
  host.cleanup();
  assert.equal(host.requests[0].signal.aborted, true);
});

test("cancel ignores late responses and cannot clear a newer request; resume restores elapsed time", async () => {
  const host = workspaceHost();
  host.render(); host.runEffects(); await flush();
  const first = host.requests[0];
  button(host.render(), "Cancel preparation")();
  assert.equal(first.signal.aborted, true);
  button(host.render(), "Start 50-question quiz")();
  const second = host.requests[1];
  first.resolve(attempt()); await flush();
  assert.match(renderToStaticMarkup(host.render()), /Preparing your 50-question quiz/);
  assert.doesNotMatch(renderToStaticMarkup(host.render()), /Saved question 3/);
  second.resolve(attempt()); await flush();
  const html = renderToStaticMarkup(host.render());
  assert.match(html, /Saved question 3/);
  assert.match(html, /45:00/);
  assert.match(html, /1 answered/);
  assert.match(html, /aria-pressed="true"/);
  assert.doesNotMatch(html, /Preparing your 50-question quiz/);
  host.cleanup();
});

test("failed preparation removes the skeleton, keeps retry available and does not auto-loop", async () => {
  const host = workspaceHost();
  host.render(); host.runEffects(); await flush();
  host.requests[0].reject(new Error("Quiz service is unavailable")); await flush();
  const tree = host.render(), html = renderToStaticMarkup(tree);
  assert.match(html, /role="alert"/);
  assert.match(html, /Quiz service is unavailable/);
  assert.doesNotMatch(html, /aria-busy="true"/);
  host.runEffects(); await flush();
  assert.equal(host.requests.length, 1);
  button(tree, "Retry")();
  assert.equal(host.requests.length, 2);
  host.cleanup();
});

test("daily preparation keeps saved counts after failure and offers one recovery action", async () => {
  const host = workspaceHost();
  host.render(); host.runEffects(); await flush();
  host.requests[0].onProgress(20);
  host.render(); host.runEffects();
  host.requests[0].reject(new Error("We couldn't check the next questions right now.")); await flush();
  const tree = host.render(), html = renderToStaticMarkup(tree);
  assert.match(html, /20 of 50 questions ready/);
  assert.match(html, /Your prepared questions stay saved/);
  assert.match(html, /Your quiz hasn’t opened yet/);
  assert.match(html, /role="alert"/);
  assert.equal((html.match(/Retry quiz/g) ?? []).length, 1);
  assert.doesNotMatch(html, /Start 50-question quiz|aria-busy="true"/);
  host.runEffects(); await flush();
  assert.equal(host.requests.length, 1);
  button(tree, "Retry quiz")();
  const retried = renderToStaticMarkup(host.render());
  assert.match(retried, /20 of 50 questions ready/);
  assert.match(retried, /aria-busy="true"/);
  assert.doesNotMatch(retried, /role="alert"/);
  assert.equal(host.requests.length, 2);
  host.cleanup();
});

test("progress updates do not restart the elapsed slow-preparation warning", async () => {
  const host = workspaceHost();
  host.render(); host.runEffects(); await flush();
  const delayedEntry = [...host.timers.entries()].find(([, timer]) => timer.ms === 25_000);
  assert.ok(delayedEntry);
  const [timerId, delayed] = delayedEntry;
  for (const prepared of [10, 20, 30]) {
    host.requests[0].onProgress(prepared);
    host.render(); host.runEffects(); await flush();
    assert.equal(host.timers.get(timerId), delayed);
    assert.equal([...host.timers.values()].filter(timer => timer.ms === 25_000).length, 1);
  }
  delayed.fn();
  assert.match(renderToStaticMarkup(host.render()), /Still preparing your questions/);
  host.requests[0].onProgress(40);
  host.render(); host.runEffects();
  assert.match(renderToStaticMarkup(host.render()), /Still preparing your questions/);
  host.cleanup();
});

test("slow preparation is bounded, abortable and has reduced-motion styling", async () => {
  const host = workspaceHost();
  host.render(); host.runEffects(); await flush();
  host.render(); host.runEffects();
  const delayed = [...host.timers.values()].find(timer => timer.ms === 25_000);
  delayed.fn();
  assert.match(renderToStaticMarkup(host.render()), /Still preparing your questions/);
  [...host.timers.values()].find(timer => timer.ms === 360_000).fn();
  assert.equal(host.requests[0].signal.aborted, true);
  host.requests[0].reject(new DOMException("Aborted", "AbortError")); await flush();
  assert.match(renderToStaticMarkup(host.render()), /couldn&#x27;t be opened in time/);
  const css = read("../app/practice/PracticeQuestionSkeleton.module.css");
  assert.match(css, /prefers-reduced-motion:reduce[^]*animation: none/);
  host.cleanup();
});

test("route navigation, topic lookup and starting focus time all provide pending UI", () => {
  assert.match(read("../app/subjects/loading.tsx"), /<PracticeQuestionSkeleton/);
  const subjects = read("../app/subjects/page.tsx");
  assert.match(subjects, /<PracticeQuestionSkeleton count=\{50\}/);
  assert.match(subjects, /getStudyTask\(accessToken,taskId,controller.signal\)/);
  assert.match(subjects, /controller.abort\(\),30_000/);
  const progress = read("../app/progress/TodayPlan.tsx");
  assert.match(progress, /Starting study…/);
  assert.match(progress, /className=\{s.focusSkeleton\}/);
  assert.match(progress, /setPendingTaskAction\(action\)/);
  assert.match(progress, /changeStudyTask\(accessToken,task.id,action,controller.signal\)/);
});

test("all quiz and focus APIs forward abort signals without changing saved-answer payloads", async () => {
  const host = queryHarness(() => ({status:"ready",attempt:{questions:[{}]}}));
  const calls = host.calls;
  const plan = host.api("study-plan-api"), study = host.api("study-api");
  const signal = new AbortController().signal;
  await plan.getStudyTask("token", "one&two", signal);
  await plan.changeStudyTask("token", "one&two", "start", signal);
  await plan.startDailyQuiz("token", "one&two", signal);
  await study.startPracticeAttempt("token", { subject_slug: "english", question_count: 50 }, signal);
  await study.startSimilarAttempt("token", { subject_slug: "english", question_count: 50 }, signal);
  assert.equal(calls.length, 5);
  assert.ok(calls.every(call => call.init.signal && !call.init.signal.aborted));
  assert.match(calls[2].path, /quiz\/prepare$/);
  assert.match(calls[0].path, /one%26two/);
  assert.deepEqual(JSON.parse(calls[1].init.body), { action: "start" });
});

test("Save & next advances immediately on a slow connection and submission waits for ordered writes", async () => {
  const host = workspaceHost();
  host.render(); host.runEffects(); await flush();
  host.requests[0].resolve(attempt()); await flush();
  host.render(); host.runEffects();
  button(host.render(), "Save &amp; next")();
  assert.match(renderToStaticMarkup(host.render()), /Saved question 4/);
  assert.equal(host.saves.length, 1);
  assert.equal(host.saves[0].input[4], 3);
  button(host.render(), "Skip &amp; next")();
  button(host.render(), "Skip &amp; next")();
  assert.match(renderToStaticMarkup(host.render()), /Saved question 6/);
  assert.equal(host.saves.length, 1); // Only one write in flight.
  button(host.render(), "Submit set")(); await flush();
  assert.equal(host.completions.length, 0);
  host.saves[0].resolve(null); await flush();
  assert.equal(host.saves.length, 2);
  assert.equal(host.saves[1].input[4], 5); // Intermediate snapshots coalesced.
  host.saves[1].resolve(null); await flush();
  assert.equal(host.completions.length, 1);
  assert.equal(host.completions[0].input[1], "saved-quiz");
  host.completions[0].resolve({review:[]}); await flush();
  host.cleanup();
});

test("daily quizzes disclose revision questions without adding a banner for fresh sets", async () => {
  for (const repeated_questions of [0, 1, 5]) {
    const host = workspaceHost();
    host.render(); host.runEffects(); await flush();
    host.requests[0].resolve(attempt({ repeated_questions })); await flush();
    const html = renderToStaticMarkup(host.render());
    if (repeated_questions === 0) assert.doesNotMatch(html, /from earlier practice/);
    else assert.match(html, new RegExp(`${repeated_questions} ${repeated_questions === 1 ? "question from earlier practice is" : "questions from earlier practice are"} included for revision\\.`));
    host.cleanup();
  }
});
