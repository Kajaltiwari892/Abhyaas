import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { getPreparationTarget, partitionPreparationSubjects } from "../lib/academy-preference.ts";
import { academies } from "../app/exam-info/exam-guide-data.ts";

const subjects = [
  { slug: "elementary-mathematics" }, { slug: "general-knowledge" }, { slug: "english" },
];

test("academy targets match the guide, with two OTA subjects and three for other routes", () => {
  for (const academy of academies) {
    const target = getPreparationTarget(academy.id);
    assert.equal(target.code, academy.code);
    assert.equal(target.subjects.length, academy.papers);
    assert.equal(target.subjects.some((item) => item.slug === "elementary-mathematics"), academy.id !== "ota");
  }
});

test("OTA prioritises English and GK while preserving optional Maths", () => {
  const snapshot = structuredClone(subjects);
  const groups = partitionPreparationSubjects(subjects, "ota");
  assert.deepEqual(groups.required.map((item) => item.slug), ["english", "general-knowledge"]);
  assert.deepEqual(groups.optional.map((item) => item.slug), ["elementary-mathematics"]);
  assert.deepEqual(subjects, snapshot);
  for (const id of ["ima", "ina", "afa"]) {
    assert.equal(partitionPreparationSubjects(subjects, id).required.length, 3);
    assert.equal(partitionPreparationSubjects(subjects, id).optional.length, 0);
  }
});

test("unset or unknown targets do not hide subjects or infer a target", () => {
  for (const id of [null, undefined, "unknown", "__proto__", "toString", "OTA", 42]) {
    assert.equal(getPreparationTarget(id), null);
    assert.deepEqual(partitionPreparationSubjects(subjects, id), { required: subjects, optional: [] });
  }
  assert.deepEqual(partitionPreparationSubjects([], "ota"), { required: [], optional: [] });
});

test("exploring and saving are separate, and target advice stays outside active sets", () => {
  const guide = readFileSync(new URL("../app/exam-info/ExamGuide.tsx", import.meta.url), "utf8");
  assert.match(guide, /onClick=\{\(\) => \{ setExploring\(item.id\); setFeedback\(undefined\); \}\}/);
  assert.match(guide, /Set \{academy.code\} as my target/);
  assert.match(guide, /saveTarget\(null\)/);
  const practice = readFileSync(new URL("../app/practice/PracticeWorkspace.tsx", import.meta.url), "utf8");
  assert.match(practice, /!attempt && !summary && tab === "practice" && <PreparationTarget/);
  assert.match(practice, /subjectGroups.optional.map/);
  const page = readFileSync(new URL("../app/subjects/page.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(page, /target_academy/); // A preference change must not remount a set.
});
