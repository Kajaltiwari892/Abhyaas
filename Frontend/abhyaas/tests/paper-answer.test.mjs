import assert from "node:assert/strict";
import test from "node:test";
import { hasStoredAnswer, paperScoreDescription } from "../lib/paper-answer.ts";
import { solutionLabel } from "../lib/paper-solution.ts";

test("checked answers can be revealed without being called official", () => {
  assert.equal(hasStoredAnswer({ is_verified: false, is_scorable: true, correct_index: 2 }), true);
  assert.equal(hasStoredAnswer({ is_verified: false, is_scorable: false, correct_index: 0 }), false);
  assert.equal(hasStoredAnswer({ is_scorable: true, correct_index: null }), false);
  assert.equal(solutionLabel("reviewed"), "Checked practice answer");
  assert.equal(solutionLabel("provisional"), "Provisional answer");
});

test("a partial practice score never claims to be the full official score", () => {
  assert.equal(paperScoreDescription({ scored_questions: 30, total_questions: 120, unscored_questions: 90, score_basis: "practice" }), "Practice score based on 30 of 120 questions. 90 not included yet.");
  assert.doesNotMatch(paperScoreDescription({ scored_questions: 120, total_questions: 120, unscored_questions: 0, score_basis: "practice" }), /official|pending|not included/);
});
