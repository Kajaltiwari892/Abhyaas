import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { practiceChoices, practiceSetSize } from "../lib/practice-plan.ts";

test("similar sets create the requested count independently of a finite bank", () => {
  assert.equal(practiceSetSize("similar", 50, { total: 4, unseen: 0 }), 50);
  assert.equal(practiceSetSize("similar", 25), 25);
  assert.equal(practiceSetSize("similar", 120), 50);
  assert.deepEqual(practiceChoices("similar"), [10, 25, 50]);
});

test("bank and mixed sets use honest counts, without fake extra questions", () => {
  assert.equal(practiceSetSize("fresh", 50, { total: 74, unseen: 60 }), 50);
  assert.equal(practiceSetSize("fresh", 50, { total: 74, unseen: 5 }), 5);
  assert.equal(practiceSetSize("mixed", 50, { total: 74, unseen: 0 }), 50);
  assert.equal(practiceSetSize("fresh", 50), 0);
  assert.equal(practiceSetSize("fresh", 50, { total: 74, unseen: 0 }), 0);
});

test("workspace offers a way forward, with honest AI labels and saved history", () => {
  const source = readFileSync(new URL("../app/practice/PracticeWorkspace.tsx", import.meta.url), "utf8");
  assert.ok(!source.includes("You’ve tried all"));
  assert.ok(!source.includes("Choose another topic"));
  assert.ok(source.includes("startSimilarAttempt"));
  assert.ok(source.includes("<PracticeQuestionSkeleton {...openingSet}"));
  assert.ok(source.includes("not exam questions"));
  assert.ok(source.includes("question_mode"));
  assert.ok(source.includes("pending?.abort()"));
});
