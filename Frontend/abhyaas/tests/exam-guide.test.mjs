import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";
import { academies, examSource, getAcademyGuide, writtenPapers } from "../app/exam-info/exam-guide-data.ts";

test("four distinct academy routes share the correct written-paper totals", () => {
  assert.deepEqual(academies.map(({ id }) => id), ["ima", "ina", "afa", "ota"]);
  for (const academy of academies) {
    const papers = writtenPapers.filter((paper) => academy.id !== "ota" || paper.ota);
    assert.equal(papers.length, academy.papers);
    assert.equal(papers.reduce((sum, paper) => sum + paper.marks, 0), academy.id === "ota" ? 200 : 300);
    assert.ok(academy.education && academy.menEligibility && academy.womenEligibility && academy.photoAlt);
  }
  assert.ok(writtenPapers.every((paper) => paper.hours === 2));
});

test("switching academy updates required papers, time and marks together", () => {
  for (const id of ["ota", "ima", "ina", "afa", "ota"]) {
    const guide = getAcademyGuide(id);
    assert.equal(guide.academy.id, id);
    assert.deepEqual(guide.papers.map((paper) => paper.id), id === "ota"
      ? ["english", "gk"] : ["english", "gk", "maths"]);
    assert.equal(guide.writtenMarks, id === "ota" ? 200 : 300);
    assert.equal(guide.writtenHours, id === "ota" ? 4 : 6);
    assert.equal(guide.academy.entry, id === "ota" ? "Men & women" : "Men only");
  }
});

test("academy photos are bundled locally and the official source is cycle-labelled", () => {
  for (const id of ["ina", "afa", "ota"]) assert.ok(existsSync(new URL(`../public/exam-info/${id}.jpg`, import.meta.url)));
  assert.ok(existsSync(new URL("../assets/img6.jpg", import.meta.url)));
  assert.equal(new URL(examSource.notification).hostname, "www.upsc.gov.in");
  assert.match(examSource.label, /2026/);
});

test("guide navigation has real destinations, labelled selection and native disclosures", () => {
  const guide = readFileSync(new URL("../app/exam-info/ExamGuide.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(guide, /href="\/exam-info"/);
  for (const id of ["academies", "exam-pattern", "selection", "questions"]) {
    assert.ok(guide.includes(`href="#${id}"`));
    assert.ok(guide.includes(`id="${id}"`));
  }
  assert.match(guide, /aria-pressed=\{active\}/);
  assert.match(guide, /aria-controls="academy-details"/);
  assert.match(guide, /<details><summary>/);
  assert.match(guide, /<table/);
});
