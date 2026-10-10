import test from "node:test";
import assert from "node:assert/strict";
import { paperArchiveYears, filterPaperArchive, paperAvailability, paperOpeningMode } from "../lib/paper-archive.ts";

const papers = [
  { year: 2016, cycle: "II", subject_slug: "english" },
  { year: 2027, cycle: "I", subject_slug: "english" },
  { year: 2024, cycle: "II", subject_slug: "general-knowledge" },
  { year: 2027, cycle: "I", subject_slug: "general-knowledge" },
];

test("archive years come from data, including old and future years", () => {
  assert.deepEqual(paperArchiveYears(papers), [2027, 2024, 2016]);
  assert.deepEqual(paperArchiveYears([]), []);
});

test("year, cycle and subject filters combine without changing the full year list", () => {
  assert.equal(filterPaperArchive(papers, { year: "2027", cycle: "I", subject: "english" }).length, 1);
  assert.equal(filterPaperArchive(papers, { year: "2016", cycle: "I", subject: "" }).length, 0);
  assert.equal(filterPaperArchive(papers, { year: "", cycle: "", subject: "" }).length, 4);
  assert.deepEqual(paperArchiveYears(papers), [2027, 2024, 2016]);
});

test("PDF-only and partial papers are not labelled complete interactive mocks", () => {
  assert.equal(paperAvailability({ available_question_count: 0, official_question_count: 120 }), "pdf");
  assert.equal(paperAvailability({ available_question_count: 5, official_question_count: 120 }), "partial");
  assert.equal(paperAvailability({ available_question_count: 120, official_question_count: 120 }), "interactive");
});

test("partial chapter collections open for study without a full-paper timer", () => {
  const partial = { available_question_count: 2, official_question_count: 120 };
  const complete = { available_question_count: 120, official_question_count: 120 };
  assert.equal(paperOpeningMode(partial, "mock"), "review");
  assert.equal(paperOpeningMode(partial, "review"), "review");
  assert.equal(paperOpeningMode(complete, "mock"), "mock");
  assert.equal(paperOpeningMode(complete, "review"), "review");
});
