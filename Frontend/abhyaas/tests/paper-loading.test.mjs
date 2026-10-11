import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Render the actual TSX component without a browser or an additional test dependency.
const require = createRequire(import.meta.url);
const component = readFileSync(new URL("../app/components/PaperQuestionSkeleton.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(component, {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
const loaded = { exports: {} };
new Function("require", "module", "exports", compiled)(
  (id) => id.endsWith(".module.css") ? { default: new Proxy({}, { get: (_, key) => String(key) }) } : require(id),
  loaded, loaded.exports,
);

test("the question skeleton names the selected subject and has four decorative options", () => {
  for (const subject of ["English", "General Knowledge", "Elementary Mathematics"]) {
    const html = renderToStaticMarkup(createElement(loaded.exports.default, { subject }));
    assert.ok(html.includes(`Preparing your ${subject} questions…`));
    assert.match(html, /role="status" aria-live="polite"/);
    assert.match(html, /class="paper-question-layout" aria-hidden="true"/);
    assert.equal((html.match(/class="option"/g) ?? []).length, 4);
    assert.doesNotMatch(html, /<button|role="progressbar"/); // No pretend actions or fake completion.
  }
});

test("paper opening renders pending UI before awaiting data and keeps stale responses out", () => {
  const page = readFileSync(new URL("../app/papers/page.tsx", import.meta.url), "utf8");
  const opening = page.slice(page.indexOf("const openPaper ="), page.indexOf("const submitMock ="));
  const pending = opening.indexOf("setOpeningPaper({ paper, mode: nextMode })");
  assert.ok(pending >= 0 && pending < opening.indexOf("await Promise.all"));
  assert.match(page, /const workspaceOpen = Boolean\(mode \|\| openingPaper\)/);
  assert.match(page, /openingPaper \? <PaperQuestionSkeleton subject=\{openingPaper.paper.subject_name\}/);
  assert.match(opening, /if \(openingRequest.current !== request\) return/);
  assert.match(opening, /if \(openingRequest.current === request\)/);
  assert.match(opening, /setOpeningPaper\(null\); setBusy\(false\)/);
  assert.match(page, /if \(mode !== "mock" \|\| !attempt \|\| remaining <= 0\) return/);
});

test("loading supports cancel, bounded waits and reduced motion", () => {
  const page = readFileSync(new URL("../app/papers/page.tsx", import.meta.url), "utf8");
  const close = page.slice(page.indexOf("const closeWorkspace ="), page.indexOf("}, [busy]);"));
  assert.ok(close.indexOf("openingRequest.current = null") < close.indexOf("pending?.abort()"));
  assert.match(page, /window.setTimeout\(\(\) => request.abort\(\), 30_000\)/);
  assert.match(page, /window.clearTimeout\(timeout\)/);
  assert.match(page, /disabled=\{busy && !openingPaper\}/);
  const css = readFileSync(new URL("../app/components/PaperQuestionSkeleton.module.css", import.meta.url), "utf8");
  assert.match(css, /prefers-reduced-motion: reduce[\s\S]*animation: none/);
});
