import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { legacyPracticeDestination } from "../lib/study-navigation.ts";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("old practice bookmarks open the unified Subjects workspace", () => {
  assert.equal(legacyPracticeDestination({}), "/subjects");
  assert.equal(legacyPracticeDestination({ subject: "general-knowledge", topic: "modern-history" }), "/subjects?subject=general-knowledge&topic=modern-history");
  assert.equal(legacyPracticeDestination({ subject: "english", view: "history" }), "/subjects?subject=english&view=history");
  assert.equal(legacyPracticeDestination({ view: "practice" }), "/subjects");
});

test("old notebook and revision links open the dedicated notebook", () => {
  assert.equal(legacyPracticeDestination({ view: "notebook" }), "/mistake-notebook");
  assert.equal(legacyPracticeDestination({ view: "notebook", revision: "saved-session" }), "/mistake-notebook?revision=saved-session");
  assert.equal(legacyPracticeDestination({ view: "notebook", subject: "english", topic: "grammar", revision: "" }), "/mistake-notebook");
});

test("duplicate, empty and unrelated parameters are handled without external redirects", () => {
  assert.equal(legacyPracticeDestination({ subject: ["english", "general-knowledge"], view: ["history", "notebook"] }), "/subjects?subject=english&view=history");
  assert.equal(legacyPracticeDestination({ subject: [], topic: "", view: "unknown", revision: "unused", next: "https://example.com", token: "secret" }), "/subjects");
  const destination = legacyPracticeDestination({ subject: "english&view=notebook", topic: "earth's interior" });
  const query = new URL(destination, "https://example.test").searchParams;
  assert.equal(query.get("subject"), "english&view=notebook");
  assert.equal(query.get("topic"), "earth's interior");
  assert.equal(query.has("view"), false);
  assert.ok(destination.startsWith("/subjects?"));
});

test("Subjects exposes one in-place workspace and keeps account and history isolation", () => {
  const page = read("../app/subjects/page.tsx");
  assert.ok(page.includes("<PracticeWorkspace"));
  assert.ok(page.includes("initialSubject={subject}"));
  assert.ok(page.includes("initialTopic={topic}"));
  assert.ok(page.includes("initialView={view}"));
  assert.ok(page.includes('user?.id ?? "guest"'));
  assert.ok(!page.includes("setSelected"));
  const workspace = read("../app/practice/PracticeWorkspace.tsx");
  assert.ok(workspace.includes('<h1>{dailyTask ? "Today’s topic quiz" : "Subjects"}</h1>'));
  assert.ok(workspace.includes("if (active) await persist()"));
  assert.ok(workspace.includes("onChange={(e) => void leave(e.target.value)}"));
  assert.ok(workspace.includes('nextTab: "practice" | "history"'));
});

test("desktop and mobile navigation expose Subjects and notebook, not another Practice page", () => {
  const shell = read("../app/components/AppShell.tsx");
  assert.ok(shell.includes('{ label: "Subjects", href: "/subjects"'));
  assert.ok(shell.includes('{ label: "Mistake notebook", href: "/mistake-notebook"'));
  assert.ok(!shell.includes('label: "Practice"'));
  assert.ok(shell.includes('["Subjects", "Mistake notebook", "Doubt solver", "Previous papers", "Progress"]'));
  assert.ok(read("../app/mistake-notebook/page.tsx").includes('active="Mistake notebook"'));
  assert.ok(read("../app/practice/MistakeNotebook.tsx").includes('`${notebookUrl}?revision='));
  assert.ok(read("../app/practice/page.tsx").includes("redirect(legacyPracticeDestination(await searchParams))"));
});
