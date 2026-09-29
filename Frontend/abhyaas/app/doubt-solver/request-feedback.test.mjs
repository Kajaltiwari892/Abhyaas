import test from "node:test";
import assert from "node:assert/strict";
import { requestFeedback } from "./request-feedback.ts";

test("brief requests do not display a distracting counter or pretend to stream an answer", () => {
  assert.deepEqual(requestFeedback(0), { label: "Preparing your response", detail: "", elapsed: "" });
  assert.equal(requestFeedback(11.9).elapsed, "");
  assert.equal(requestFeedback(0, true).label, "Reading your question image");
});

test("long requests show elapsed wait, not an invented completion percentage or count", () => {
  assert.deepEqual(requestFeedback(12.9), {
    label: "Still preparing your response",
    detail: "AI answers and large practice sets can take longer than paper lookups.",
    elapsed: "12s elapsed",
  });
  assert.match(requestFeedback(60).detail, /do not need to send your question again/);
  assert.equal(requestFeedback(125).elapsed, "125s elapsed");
});

test("invalid times are treated as a fresh request", () => {
  for (const value of [-1, Number.NaN, Number.POSITIVE_INFINITY]) {
    assert.deepEqual(requestFeedback(value), requestFeedback(0));
  }
});
