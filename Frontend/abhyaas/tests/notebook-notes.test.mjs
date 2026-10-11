import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
const css = { default: new Proxy({}, { get: (_, key) => String(key) }) };
function load(path, resolve = require) {
  const compiled = ts.transpileModule(read(path), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const loaded = { exports: {} };
  new Function("require", "module", "exports", compiled)(resolve, loaded, loaded.exports);
  return loaded.exports;
}
const Text = load("../app/practice/NotebookText.tsx", id => {
  if (id === "@/lib/paper-format") return load("../lib/paper-format.ts");
  if (id === "@/lib/paper-text") return load("../lib/paper-text.ts");
  return require(id);
}).default;
const { default: Note, noteExplanation, noteHelp, noteCitation } = load("../app/practice/MistakeNote.tsx", id => {
  if (id.endsWith(".css")) return css;
  if (id === "./NotebookText") return { default: Text };
  if (id === "next/link") return { default: ({ children, href, className }) => createElement("a", { href, className }, children) };
  return require(id);
});
const fixture = {
  question_key: "practice:grammar", subject: "English", subject_slug: "english", topic: "Subject–verb agreement",
  prompt: "Choose the correct sentence.", context: null,
  options: ["She goes home.", "She go home.", "She going home.", "She gone home."],
  correct_index: 0, selected_index: 1, mistake_selected_index: 1,
  explanation: "A singular subject takes 'goes'.", reason: "wrong", state: "pending",
  last_attempt_at: "2026-10-10T10:00:00Z", revision_ready: true, review_available: true,
  source_label: "CDS English practice", source_url: "https://upsc.gov.in/paper.pdf", source_page_url: "/papers/example/page-1.webp",
};
const render = patch => renderToStaticMarkup(createElement(Note, { item: { ...fixture, ...patch }, number: 1 }));

test("mistake notes expose the answer comparison, real explanation and next step without opening an accordion", () => {
  const html = render();
  assert.match(html, /<article[^>]+aria-labelledby=/);
  assert.match(html, /Your answer/);
  assert.match(html, /Correct answer/);
  assert.match(html, /Understand the correction/);
  assert.match(html, /A singular subject takes/);
  assert.match(html, /Next time/);
  assert.match(html, /Compare your reasoning with the explanation/);
  assert.ok(html.indexOf("Understand the correction") < html.indexOf("<details"));
  assert.match(html, /Original paper/);
  assert.match(html, /href="https:\/\/upsc.gov.in\/paper.pdf"/);
  assert.match(html, /Original question/);
  assert.doesNotMatch(html, /You failed|careless|You didn.t/);
});

test("revised notes preserve the earlier wrong choice, not the latest correct choice", () => {
  const html = render({ selected_index: 0, state: "resolved" });
  assert.match(html, />Revised</);
  assert.match(html, /Your earlier answer/);
  const earlier = html.split('aria-label="Your earlier answer"')[1].split("</section>")[0];
  assert.match(earlier, /She go home/);
  assert.doesNotMatch(earlier, /She goes home/);
});

test("skipped notes use reassuring wording and never treat option zero as a missing answer", () => {
  const html = render({ selected_index: null, mistake_selected_index: null, reason: "skipped" });
  assert.match(html, /Left unanswered/);
  assert.match(html, /Let’s work through it/);
  assert.match(html, /Let’s understand it/);
  assert.match(html, /She goes home/);
  const zero = render({ correct_index: 1, selected_index: 0, mistake_selected_index: 0 });
  const earlier = zero.split('aria-label="Your answer"')[1].split("</section>")[0];
  assert.match(earlier, /She goes home/);
  assert.doesNotMatch(earlier, /isn’t available/);
});

test("missing explanations and key-only records cannot pose as a concept explanation", () => {
  for (const explanation of ["", "Answer verification pending.", "The official UPSC Series A answer key marks option (a).", "The provisional UPSC Series A answer key marks option (c)."] ) {
    assert.equal(noteExplanation(explanation), "");
    const html = render({ explanation });
    assert.match(html, /Help me understand this/);
    assert.doesNotMatch(html, /step-by-step explanation hasn.t been added yet|Understand the correction|Next time/);
    assert.doesNotMatch(html, /Answer verification pending|answer key marks/);
  }
  assert.equal(noteExplanation(fixture.explanation), fixture.explanation);
});

test("paper references are readable without losing original source information", () => {
  assert.equal(noteCitation("UPSC CDS II 2026 · Q55 · provisional answer"), "CDS II 2026 · Question 55");
  assert.equal(noteCitation("CDS I 2025 · Q80 · Official UPSC Series A key"), "CDS I 2025 · Question 80");
  assert.equal(noteCitation(" CDS English practice "), "CDS English practice");
  assert.equal(noteCitation("An archived question"), "An archived question");
  const html = render({ source_label: "UPSC CDS II 2026 · Q55 · provisional answer" });
  const footer = html.split('<footer class="noteFooter">')[1].split("</footer>")[0];
  assert.match(footer, /CDS II 2026 · Question 55<\/span>/);
  assert.match(footer, /title="UPSC CDS II 2026 · Q55 · provisional answer"/);
  assert.match(footer, /<time dateTime="2026-10-10T10:00:00Z">Practised on 10 Oct 2026<\/time>/);
  assert.match(footer, /class="noteLinks"/);
  assert.match(footer, /Original question/);
  assert.match(footer, /Original paper/);
  assert.doesNotMatch(footer, /class="sources"/);
  assert.match(html, /This answer is provisional and may change/);
});

test("notebook paper decorations are non-interactive and answer colours retain readable contrast", () => {
  const html = render();
  assert.match(html, /<div class="paperBinding" aria-hidden="true">(?:<span><\/span>){6}<\/div>/);
  const styles = read("../app/practice/notebook.module.css");
  assert.match(styles, /\.note::after[^}]+pointer-events:none[^}]+clip-path:polygon/);
  assert.match(styles, /\.noteFooter[^}]+background:transparent/);
  assert.match(styles, /\.noteFooter[^}]+padding:12px 0 0/);
  const luminance = hex => {
    const rgb = hex.match(/[\da-f]{2}/gi).map(value => parseInt(value, 16) / 255);
    const linear = rgb.map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
    return linear[0] * .2126 + linear[1] * .7152 + linear[2] * .0722;
  };
  const contrast = (foreground, background) => {
    const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
    return (values[0] + .05) / (values[1] + .05);
  };
  const colour = name => styles.match(new RegExp(`--${name}:(#[\\da-f]{6})`))[1];
  const accent = styles.match(/\.note\s*\{\s*--accent:(#[\da-f]{6})/)[1];
  assert.ok(contrast(colour("note-text"), colour("note-surface")) >= 4.5);
  assert.ok(contrast(colour("note-muted"), colour("note-surface")) >= 4.5);
  assert.ok(contrast(colour("note-warm"), colour("note-warm-bg")) >= 4.5);
  assert.ok(contrast(accent, colour("note-green-bg")) >= 4.5);
});

test("help links carry full short questions and respect tutor limits without cutting long passages", () => {
  const help = noteHelp(fixture);
  const params = new URLSearchParams(help.href.split("?")[1]);
  assert.equal(params.get("subject"), "english");
  assert.ok(params.get("question").includes(fixture.prompt));
  for (const option of fixture.options) assert.ok(params.get("question").includes(option));
  const long = noteHelp({ ...fixture, context: "A long passage. ".repeat(200) });
  const longParams = new URLSearchParams(long.href.split("?")[1]);
  assert.equal(long.label, "Help me revise this topic");
  assert.ok(longParams.get("question").length <= 1500);
  assert.ok(!longParams.get("question").includes("A long passage"));
  assert.match(render({ source_label: "UPSC provisional answer" }), /answer is provisional and may change/);
});

test("unreviewable questions and older APIs do not show made-up earlier answers", () => {
  const missing = render({ review_available: false, explanation: "This must not be shown." });
  assert.match(missing, /can’t confirm the answer here yet/);
  assert.doesNotMatch(missing, /This must not be shown/);
  const old = render({ mistake_selected_index: undefined, selected_index: 0, state: "resolved" });
  const earlier = old.split('aria-label="Your earlier answer"')[1].split("</section>")[0];
  assert.match(earlier, /earlier choice isn’t available/);
  assert.doesNotMatch(earlier, /She goes home/);
  assert.match(render({ correct_index: 100 }), /can’t confirm the answer/);
});

test("passages, every option, paper notation and safe text rendering survive the redesign", () => {
  const html = render({ context: "Read the full passage.\nSecond line.", prompt: String.raw`Select \underline{this} fraction: \frac{1}{2}. <img src=x onerror=alert(1)>`, last_attempt_at: "bad-date" });
  assert.match(html, /Read passage &amp; all options/);
  assert.match(html, /Second line/);
  for (const option of fixture.options) assert.ok(html.includes(option));
  assert.match(html, /<u>this<\/u>/);
  assert.match(html, /\(1\)\/\(2\)/);
  assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<img|Invalid Date/);
});

test("notebook keeps existing revision, pagination and saved history while using notes-first layout", () => {
  const source = read("../app/practice/MistakeNotebook.tsx");
  assert.match(source, /<MistakeNote/);
  assert.doesNotMatch(source, /<NotebookCard/);
  assert.match(source, /Clear filters/);
  assert.match(source, /revisionCount/);
  assert.match(source, /page\.has_more \|\| filters\.offset > 0/);
  assert.match(source, /recent_sessions\.map/);
  const styles = read("../app/practice/notebook.module.css");
  assert.match(styles, /max-width:520px/);
  assert.match(styles, /data-theme="light"/);
  assert.match(styles, /prefers-reduced-motion:reduce/);
});
