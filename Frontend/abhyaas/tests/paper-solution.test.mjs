import assert from "node:assert/strict";
import test from "node:test";
import { solutionContinuation, solutionLabel } from "../lib/paper-solution.ts";

test("AI answers are never labelled verified and key conflicts are visible", () => {
  assert.equal(solutionLabel("ai"), "AI solution · official verification pending");
  assert.match(solutionLabel("verified"), /explanation may be AI-generated/);
  assert.match(solutionLabel("key_conflict"), /needs review/);
  assert.match(solutionLabel("unexpected"), /Uncertain/);
});

test("continue shows the next bounded range including the last short batch", () => {
  assert.equal(solutionContinuation(11, 120), "Continue · Q11–20");
  assert.equal(solutionContinuation(111, 116), "Continue · Q111–116");
});
