import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { queryHarness, session } from "./helpers/query-harness.mjs";
import { formatPaperText } from "../lib/paper-format.ts";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
function loadApi() {
  const host = queryHarness();
  host.controller.completeAuthentication(session("student", "student-token"));
  return { ...host, api: host.api("notebook-api") };
}

test("notebook filters and account authorization reach the API", async () => {
  const { api, calls } = loadApi();
  const signal = new AbortController().signal;
  await api.getNotebook("student-token", { subject:"general-knowledge", reason:"skipped", state:"resolved", offset:20 }, signal);
  const request = calls[0];
  const query = new URLSearchParams(request.path.split("?")[1]);
  assert.equal(query.get("subject"), "general-knowledge");
  assert.equal(query.get("reason"), "skipped");
  assert.equal(query.get("state"), "resolved");
  assert.equal(query.get("offset"), "20");
  assert.equal(request.init.headers.Authorization, "Bearer student-token");
  assert.notEqual(request.init.signal, signal); // Shared fetch outlives an individual reader.
  assert.equal(request.init.signal.aborted, false);
});

test("revision checkpoints preserve option zero and cleared answers without sending keys", async () => {
  const { api, calls } = loadApi();
  await api.saveRevision("token", "session", 2, { "practice:a":0, "paper:b":null }, true);
  const request = calls[0];
  assert.equal(request.init.method, "PATCH");
  assert.equal(request.init.keepalive, true);
  assert.deepEqual(JSON.parse(request.init.body), {
    current_position:2,
    answers:[{question_key:"practice:a", selected_index:0}, {question_key:"paper:b", selected_index:null}],
  });
});

test("revision start and completion use separate session endpoints, not exam scores", async () => {
  const { api, calls } = loadApi();
  await api.startRevision("token", "", "wrong", 10);
  await api.finishRevision("token", "session", 0, {});
  assert.equal(calls[0].path, "/notebook/sessions");
  assert.deepEqual(JSON.parse(calls[0].init.body), {subject:null, reason:"wrong", question_count:10});
  assert.equal(calls[1].path, "/notebook/sessions/session/complete");
  assert.deepEqual(JSON.parse(calls[1].init.body), {current_position:0, answers:[]});
});

test("paper notation stays readable, including nested fractions and source spacing", () => {
  assert.equal(formatPaperText(String.raw`\frac{x^{2}}{\sqrt{\alpha}}`), "(x²)/(√(α))");
  assert.equal(formatPaperText(String.raw`\theta \le 90^{\circ}`), "θ ≤ 90^(°)");
  assert.equal(formatPaperText("Choose ", false), "Choose ");
  assert.equal(formatPaperText(" this.", false), " this.");
});

test("notebook is reachable from practice, progress and submitted papers", () => {
  for (const file of ["../app/practice/PracticeWorkspace.tsx", "../app/progress/page.tsx", "../app/papers/page.tsx"]) {
    assert.ok(read(file).includes("/mistake-notebook"));
  }
  const component = read("../app/practice/MistakeNotebook.tsx");
  assert.ok(component.includes("await queue.current.catch"));
  assert.ok(component.includes("controller.abort()"));
  assert.ok(component.includes("old.result && !result ? old"));
  assert.ok(component.includes("aria-pressed={answers[question.question_key] === i}"));
  assert.ok(!component.includes("dangerouslySetInnerHTML"));
  assert.ok(read("../app/practice/notebook.module.css").includes("prefers-reduced-motion:reduce"));
});

 test("notebook revisits share data and revision writes invalidate it", async () => {
  const { api, calls, controller } = loadApi();
  controller.completeAuthentication(session("one", "one"));
  const filters = { subject: "", reason: "all", state: "pending", offset: 0 };
  await Promise.all([api.getNotebook("one", filters), api.getNotebook("one", filters)]);
  await api.getNotebook("one", filters);
  assert.equal(calls.length, 1);
  controller.completeAuthentication(session("two", "two"));
  await api.getNotebook("two", filters);
  assert.equal(calls.length, 2);
  await api.finishRevision("two", "revision", 0, {});
  await api.getNotebook("two", filters);
  assert.equal(calls.length, 4);
 });
